import argparse
import pickle
import os
import re
import time
from functools import wraps

import spacy
import yaml
from attrdict import AttrDict

import transformers
from transformers import TFRobertaModel
from transformers import AutoTokenizer
import pandas as pd

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import Row
from pyspark.sql.functions import explode, col, expr, array_join, upper, left, rank
from pyspark.sql.functions import lit, udf, monotonically_increasing_id
from pyspark.sql.functions import unix_timestamp, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, IntegerType, BinaryType, BooleanType, LongType

from openai import OpenAI
import json
from distutils.util import strtobool
from src.utils import prompt_direct_inferring, prompt_direct_inferring_masked, prompt_for_aspect_inferring


# polarity_key = {0:positive, 1:negative, 2:neutral}

# indexs 0, 1, 6, 8 from
# laptops_test_gold_pkl_file = '/Users/jordanharris/Code/PycharmProjects/THOR-GEN/data/laptops/Laptops_Test_Gold_Implicit_Labeled_preprocess_finetune.pkl'
# indexs 0, 2, from
# laptops_train_gold_pkl_file = '/Users/jordanharris/Code/PycharmProjects/THOR-GEN/data/laptops/Laptops_Train_v2_Implicit_Labeled_preprocess_finetune.pkl'
# data_pkl = {
#         'raw_texts': ["boot time is super fast, around anywhere from 35 seconds to 1 minute.",
#                       "tech support would not fix the problem unless i bought your plan for $150 plus.",
#                       "other than not being a fan of click pads (industry standard these days) and the lousy internal speakers, it's hard for me to find things about this notebook i don't like, especially considering the $350 price tag.",
#                       "no installation disk (dvd) is included.",
#                       "i charge it at night and skip taking the cord with me because of the good battery life.",
#                       "the tech guy then said the service center does not do 1-to-1 exchange and i have to direct my concern to the 'sales' team, which is the retail shop which i bought my netbook from."],
#         'raw_aspect_terms': ["Boot time", "tech support", "price tag", "installation disk (DVD)", "sound output quality", "cord", "service center"],
#         'bert_tokens': [[101, 9573, 2051, 2003, 3565, 3435, 1010, 2105, 5973, 2013, 3486, 3823, 2000, 1015, 3371, 1012, 102],
#                         [101, 6627, 2490, 2052, 2025, 8081, 1996, 3291, 4983, 1045, 4149, 2115, 2933, 2005, 1002, 5018, 4606, 1012, 102],
#                         [101, 2060, 2084, 2025, 2108, 1037, 5470, 1997, 11562, 19586, 1006, 3068, 3115, 2122, 2420, 1007, 1998, 1996, 10223, 6508, 4722, 7492, 1010, 2009, 1005, 1055, 2524, 2005, 2033, 2000, 2424, 2477, 2055, 2023, 14960, 1045, 2123, 1005, 1056, 2066, 1010, 2926, 6195, 1996, 1002, 8698, 3976, 6415, 1012, 102],
#                         [101, 2053, 8272, 9785, 1006, 4966, 1007, 2003, 2443, 1012, 102],
#                         [101, 1045, 3715, 2009, 2012, 2305, 1998, 13558, 2635, 1996, 11601, 2007, 2033, 2138, 1997, 1996, 2204, 6046, 2166, 1012, 102],
#                         [101, 1996, 6627, 3124, 2059, 2056, 1996, 2326, 2415, 2515, 2025, 2079, 1015, 1011, 2000, 1011, 1015, 3863, 1998, 1045, 2031, 2000, 3622, 2026, 5142, 2000, 1996, 1000, 4341, 1000, 2136, 1010, 2029, 2003, 1996, 7027, 4497, 2029, 1045, 4149, 2026, 5658, 8654, 2013, 1012, 102]],
#         'aspect_masks': [[0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#                          [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0],
#                          [0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0],
#                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#                          [0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]],
#         'implicits': [False, False, True, True, True, True],
#         'labels': [0, 1, 0, 2, 2, 1]
# }
#
# <sentences>
#     <sentence id="892:1">
#         <text>Boot time is super fast, around anywhere from 35 seconds to 1 minute.</text>
#         <aspectTerms>
#             <aspectTerm term="Boot time" polarity="positive" from="0" to="9" implicit_sentiment="False" opinion_words="fast"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="1144:1">
#         <text>tech support would not fix the problem unless I bought your plan for $150 plus.</text>
#         <aspectTerms>
#             <aspectTerm term="tech support" polarity="negative" from="0" to="12" implicit_sentiment="False" opinion_words="not fix"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="2185">
#         <text>High price tag, however.</text>
#         <aspectTerms>
#             <aspectTerm term="price tag" polarity="negative" from="5" to="14" implicit_sentiment="False" opinion_words="High"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="958:1">
#         <text>Other than not being a fan of click pads (industry standard these days) and the lousy internal speakers, it's hard for me to find things about this notebook I don't like, especially considering the $350 price tag.</text>
#         <aspectTerms>
#             <aspectTerm term="internal speakers" polarity="negative" from="86" to="103" implicit_sentiment="False" opinion_words="lousy"/>
#             <aspectTerm term="price tag" polarity="positive" from="203" to="212" implicit_sentiment="True"/>
#             <aspectTerm term="click pads" polarity="negative" from="30" to="40" implicit_sentiment="True"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="684:1">
#         <text>excellent in every way.</text>
#     </sentence>
#     <sentence id="282:9">
#         <text>No installation disk (DVD) is included.</text>
#         <aspectTerms>
#             <aspectTerm term="installation disk (DVD)" polarity="neutral" from="3" to="26" implicit_sentiment="True"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="2185">
#         <text>High price tag, however.</text>
#         <aspectTerms>
#             <aspectTerm term="price tag" polarity="negative" from="5" to="14" implicit_sentiment="False" opinion_words="High"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="2339">
#         <text>I charge it at night and skip taking the cord with me because of the good battery life.</text>
#         <aspectTerms>
#             <aspectTerm term="cord" polarity="neutral" from="41" to="45" implicit_sentiment="True"/>
#             <aspectTerm term="battery life" polarity="positive" from="74" to="86" implicit_sentiment="False" opinion_words="good"/>
#         </aspectTerms>
#     </sentence>
#     <sentence id="1316">
#         <text>The tech guy then said the service center does not do 1-to-1 exchange and I have to direct my concern to the "sales" team, which is the retail shop which I bought my netbook from.</text>
#         <aspectTerms>
#             <aspectTerm term="service center" polarity="negative" from="27" to="41" implicit_sentiment="True"/>
#             <aspectTerm term="&quot;sales&quot; team" polarity="negative" from="109" to="121" implicit_sentiment="True"/>
#             <aspectTerm term="tech guy" polarity="neutral" from="4" to="12" implicit_sentiment="True"/>
#         </aspectTerms>
#     </sentence>
#

# info
# negation then counter info
# how to rate information density?

def runtime(func):
        @wraps(func)
        def runtime_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            total_time = end_time - start_time
            print(f'Function {func.__name__}{args} {kwargs} Took {total_time:.4f} seconds')
            return result
        return runtime_wrapper

def rest_after_run(sleep_seconds=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"Resting for {sleep_seconds} seconds...")
            time.sleep(sleep_seconds)
            print("Starting.")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def json_error_handler(max_retries=3, delay_seconds=8, spec=''):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (json.JSONDecodeError, IndexError, ValueError, AssertionError) as e:
                    print(f"Error: {type(e).__name__} - {e}")
                    print(f"Error decoding {spec} JSON on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {delay_seconds} seconds...")
                        time.sleep(delay_seconds)
                    else:
                        print("Max retries exceeded. Run Canceled")
                        break
        return wrapper
    return decorator

class genDataset:
    def __init__(self, args):
        # cwd = os.getcwd()
        config = AttrDict(yaml.load(open(args.config, 'r', encoding='utf-8'), Loader=yaml.FullLoader))
        for k, v in vars(args).items():
            setattr(config, k, v)
        self.config = config
        self.config['openai_token'] = os.getenv("OPENAI_API_KEY")

        self.tokenizer = AutoTokenizer.from_pretrained(config.bert_model_path)
        self.nlp = spacy.load(config.spacy_model_path)

        self.spark_session = (SparkSession.builder
                              .master("local[*]")
                              .appName("TiktokComments")
                              .getOrCreate())

        self.csv_schema = StructType([
            StructField("Comment ID", StringType(), True),
            StructField("Reply to Which Comment", StringType(), True),
            StructField("User ID", StringType(), True),
            StructField("Username", StringType(), True),
            StructField("Nick Name", StringType(), True),
            StructField("Comment", StringType(), True),
            StructField("Comment Time", StringType(), True),
            StructField("Digg Count", IntegerType(), True),
            StructField("Author Digged", StringType(), True),
            StructField("Reply Count", IntegerType(), True),
            StructField("Pinned to Top", StringType(), True),
            StructField("User Homepage", StringType(), True),
        ])

        self.isa_schema = StructType([
            StructField("aspect", StringType(), True),
            StructField("aspect_mask", ArrayType(IntegerType(), True), True),
            StructField("token_ids", ArrayType(IntegerType(), True), True),
            StructField("token_type_ids", ArrayType(IntegerType(), True), True),
            StructField("attention_mask", ArrayType(IntegerType(), True), True),
            StructField("implicitness", BooleanType(), True),
            StructField("polarity", IntegerType(), True),
            StructField("raw_text", StringType(), True)
        ])

        self.final_schema = StructType([
            StructField("Comment ID", StringType(), True),
            StructField("Reply to Which Comment", StringType(), True),
            StructField("User ID", StringType(), True),
            StructField("Username", StringType(), True),
            StructField("Nick Name", StringType(), True),
            StructField("Comment", StringType(), True),
            StructField("Comment Time", StringType(), True),
            StructField("Digg Count", IntegerType(), True),
            StructField("Author Digged", StringType(), True),
            StructField("Reply Count", IntegerType(), True),
            StructField("Pinned to Top", StringType(), True),
            StructField("User Homepage", StringType(), True),
            StructField("aspect", StringType(), True),
            StructField("aspect_mask", ArrayType(IntegerType(), True), True),
            StructField("token_ids", ArrayType(IntegerType(), True), True),
            StructField("token_type_ids", ArrayType(IntegerType(), True), True),
            StructField("attention_mask", ArrayType(IntegerType(), True), True),
            StructField("implicitness", BooleanType(), True),  # based on previous error message
            StructField("polarity", IntegerType(), True),
            StructField("raw_text", StringType(), True)
        ])

        self.input_file_path = args.raw_file_path
        self.output_file_path = args.out_file_path
        self.raw_text_col = args.raw_text_col
        self.out_text_col = args.out_text_col
        self.batch_size = self.config['gen_batch_size']
        self.output_pkl_path = args.output_pkl_path

        self.processed_ids = []
        self.remaining_df = None

        self.base_df, self.raw_input_array = self.intialize_df(self.raw_text_col, self.out_text_col)
        self.model = self.config['chat_gpt_model_path']
        #self.model="gpt-3.5-turbo"


    def intialize_df(self, raw_text_column, out_text_col):
        base_df = (
            self.spark_session.read
            .schema(self.csv_schema)
            .csv(f"{self.input_file_path}", header=True, inferSchema=True)
            .withColumn("index", monotonically_increasing_id())
            .withColumn("index", monotonically_increasing_id())
            .withColumn("Comment Time", from_unixtime(unix_timestamp(col("Comment Time"), "dd/MM/yyyy, HH:mm:ss")))
            #.orderBy(col("Comment Time"))
            # .limit(self.batch_size)
        )
        print('Initialize DF')
        base_df.show(self.batch_size)

        # RDD stands for Resilient Distributed Dataset, which is a fundamental data structure in Apache Spark.It's a fault-tolerant collection of elements that can be operated on in parallel across a cluster of computers.
        raw_input_array = base_df.select(raw_text_column).rdd.flatMap(lambda x: x).collect()

        if os.path.exists(self.output_file_path):
            self.processed_df = self.spark_session.read.schema(self.final_schema).parquet(f"{self.output_file_path}")
            print('The parquet df length is: ', self.processed_df.count())
            self.processed_df.show()
            self.processed_ids = self.processed_df.select(out_text_col).distinct().rdd.flatMap(lambda x: x).collect()
        else:
            self.processed_df = self.spark_session.createDataFrame([], schema=self.csv_schema)

        self.remaining_df = base_df.filter(~base_df[raw_text_column].isin(self.processed_ids))
        print(self.remaining_df.count(), ' Rows remaining')
        self.remaining_df.show(10, truncate=False)
        return self.remaining_df, raw_input_array

    """
    The choice between using BERT or T5 (like flan-t5-base) largely depends on the specific task and the way the model was fine-tuned or trained. Both BERT and T5 are powerful transformer models but are designed with different architectures and objectives:
    1: BERT (Bidirectional Encoder Representations from Transformers) is designed to understand the context of words in a sentence by considering the words that come before and after the target word. It's primarily used for tasks like Named Entity Recognition (NER), sentiment analysis, and question answering.
    2: T5 (Text-to-Text Transfer Transformer) takes a different approach by treating every NLP problem as a text-to-text problem, meaning it converts all NLP tasks into a text-to-text format. This model is versatile and can be used for a variety of tasks, such as translation, summarization, question answering, and more.
    """
    def extract_text_tokens(self, input_array):
        # # RDD stands for Resilient Distributed Dataset, which is a fundamental data structure in Apache Spark.It's a fault-tolerant collection of elements that can be operated on in parallel across a cluster of computers.
        # self.raw_input_array = id_text_token_df.select("raw_texts").rdd.flatMap(lambda x: x).collect()
        # test = self.tokenizer.encode_plus(input_array[0])
        batch_encoded = self.tokenizer.batch_encode_plus(input_array,
                                                        # self.raw_input_array,
                                                         padding=True,
                                                         max_length=self.config.max_length,
                                                         return_tensors=None)
        print(batch_encoded)
        self.tokens = batch_encoded
        return self.tokens


    def prep_token_flatten(self, batch_df, raw_batch_array):
        zip_data = [
            (input_ids, token_type_ids, attention_mask, raw_input)
            for input_ids, token_type_ids, attention_mask, raw_input in zip(
                self.tokens.data['input_ids'],
                self.tokens.data['token_type_ids'],
                self.tokens.data['attention_mask'],
                raw_batch_array
            )
        ]

        token_nest_df = self.spark_session.createDataFrame(zip_data, ['input_ids', 'token_type_ids', 'attention_mask', self.raw_text_col])
        print('Token Nest DF')
        token_nest_df.show(n=5, truncate=False)
        print('Orig Batch')
        batch_df.show(n=5, truncate=False)
        batch_df = batch_df.join(token_nest_df, self.raw_text_col, "left").orderBy('index')

        print('Joined Batch')
        batch_df.show()
        return batch_df

    #  PySpark doesn't handle lists of lists automatically without a clear schema.
    def flatten_df(self, df, uuid, uuid_col_name, nests, flat_col_name, type):
        if type == dict:
            prep_col = []
            for x in nests:
                if isinstance(x, dict):
                    if isinstance(x[flat_col_name], list):
                        prep_col.append(x[flat_col_name])
                    else:
                        prep_col.append([x[flat_col_name]])
            zip_data = [(id, nest) for id, nest in zip(uuid, prep_col)]
            nests = self.spark_session.createDataFrame(zip_data, [uuid_col_name, flat_col_name])
        elif type == list:
            schema = StructType([
                StructField(uuid_col_name, StringType(), False),
                StructField(flat_col_name, ArrayType(ArrayType(IntegerType())), True)
            ])
            zip_data = [(id, nest) for id, nest in zip(uuid, nests)]
            nests = self.spark_session.createDataFrame(zip_data, schema=schema)

        unioned_df = df.join(nests, uuid_col_name, "left")
        unioned_df.show()
        flat_df = unioned_df.withColumn(flat_col_name, explode(unioned_df[flat_col_name])).orderBy('Index')
        flat_df.show()
        flat_list = flat_df.select(flat_col_name).rdd.flatMap(lambda x: x).collect()
        assert flat_df.count() == len(flat_list)
        return flat_list, flat_df

    @json_error_handler(max_retries=3, delay_seconds=2, spec='Base GPT Prompt')
    @rest_after_run(sleep_seconds=2)
    def prompt_gpt(self, role, prompt):
        """
        !!!!!!!THIS IS PAID!!!!!!!
        """
        GPTclient = OpenAI()
        completion = GPTclient.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ]
        )
        try:
            response = completion.choices[0].message.content
            if response == None:
                print()
            cleaned_response = re.search(r"\[.*\]$", response, re.DOTALL)
            if cleaned_response is None:
                raise ValueError("Could not extract JSON array from the response. Response: " + response)
            cleaned_response = re.sub(r"(?<!\\)'", '"', cleaned_response.string)
            response = json.loads(cleaned_response)
            if response == None:
                print()
        except (json.JSONDecodeError, AssertionError) as e:
            print("Error parsing JSON:", str(e))
            print("Cleaned Response:", cleaned_response)  # Debug the problematic content
            if response == None:
                print()

        print(response)
        assert isinstance(response, list), f"{self.model} output is read to list"
        assert isinstance(response[0], dict), f"{self.model} output is read to list"

        return response

    def generate_aspect_mask(self, sentence_tokens, aspect_tokenized):
        mask = [0] * len(sentence_tokens)
        aspect_len = len(aspect_tokenized)
        for i in range(len(sentence_tokens) - aspect_len + 1):
            if sentence_tokens[i:i + aspect_len] == aspect_tokenized:
                for j in range(i, i + aspect_len):
                    mask[j] = 1
        return mask

    def batch_generate_aspect_masks(self, index): #input_ids,
        self.aspect_masks = []
        for i, a in enumerate(self.aspects):
            encoded_aspect_token = self.tokenizer.encode(a, add_special_tokens=False)
            local_index = index[i] % self.batch_size
            self.aspect_masks.append(self.generate_aspect_mask(self.tokens.data['input_ids'][local_index], encoded_aspect_token))
        return self.aspect_masks

    def safe_strtobool(self, value):
        if isinstance(value, bool):
            return value
        return bool(strtobool(str(value)))

    def extract_aspects(self, sentence):
        new_context = f'Given the sentence "{sentence}", '
        prompt = new_context + f'which words or phrases are the aspect terms?'
        role = (
            "You are operating as a system that, given a list of sentences, you will identify the core word or phrase in each sentence that are the aspect term or target term of a sentence"
            " that other words in the sentence point to and augment. They do so either implicitly or explicitly. Return the found aspect term(s) in a list where each entry corresponds to a sentence."
            " If no aspect is found, place 'NONE' at the index of that sentence.")
        self.aspects = self.prompt_gpt(role, prompt)
        self.tokenizer.tokenize(self.aspects)
        return self.aspects

    @json_error_handler(max_retries=3, delay_seconds=2, spec='Aspects')
    @rest_after_run(sleep_seconds=4)
    def batch_extract_aspects(self, batch_input_array):
        new_context = f'Given these sentences "{batch_input_array}", '
        prompt = new_context + f'which words or phrases are the aspect terms?'
        role = (
            "You are a system that identifies the core word(s) or phrase(s) in a list of sentences, which represent the aspect or target term(s). "
            "Be sure to consider all aspects (Tangible or Intangible) that may be or reference a person, place or thing. "
            "Treat opinions or mental concepts as their own aspect when there are subjective statements or implicit sentiment made about them."
            "These are the words that other words or phrases in the sentence relate to and augment, either implicitly or explicitly."
            "Return the results as a JSON array with proper formatting, where each entry is a JSON object with one key:'aspectTerm'."
            "If a sentence contains more than one aspect term, list them together as the value for 'aspectTerm'. For example, [{'aspectTerm': 'term0'}, {'aspectTerm': ['term0', 'term1', 'term2']}, ...]."
            "If not significant aspect term is found have the value be 'NONE'. Each aspect object cooresponds to the input sentence, indexed accordingly."
            "Finally check your output for trailing commas, missing or extra brackets, correct quotation marks, and special characters."
            "Ensure the output contains only this JSON array and no additional text."
        )
        self.aspects = self.prompt_gpt(role, prompt)
        assert len(self.aspects) == self.batch_size
        return self.aspects

    def extract_polarity_implicitness(self, aspects):
        new_context = f'Given the sentence "{self.raw_input_array}", and this/these aspect term(s),"{aspects}'
        prompt = new_context + f'determine the polairty (positive, negative or neutral) of aspect term and if it is explicitely or implicitely expressed with respect to the whole sentence?'
        role = (
            "You are operating as a system that, given a sentence & aspect term pair, you will identify the sentiment/polarity of the aspect term within the context of the given sentence."
            "Polarity is either positive, negative or neutral {0, 1, 2}. Then determine if the expression is implicit or explicit (True or False)."
            "Return each found polarity (numeric) and implicitness (boolean) as a tuple (numeric, boolean) in a list where each entry corresponds to the input index of the sentence-aspect pair."
            "If the value of the aspect is NONE, return an object with the polarity calculated as normal but with the 'implicitness' set to 'False'. eg. {'polarity': 2, 'implicitness': 'False'} at the index of that apect input."
        )
        self.polarity_implicitness = self.prompt_gpt(role, prompt)
        return self.polarity_implicitness

    @json_error_handler(max_retries=3, delay_seconds=2, spec='Polarity & Implicits')
    @rest_after_run(sleep_seconds=4)
    def batch_extract_polarity_implicitness(self, batch_input_array, aspects):
        new_context = f'Given these sentences "{batch_input_array}" and aspect term pairs"{aspects}" which are of length {len(aspects)}, '
        prompt = new_context + f'determine the polairty (positive, negative or neutral) of aspect term and if it is explicitely or implicitely expressed with respect to the whole sentence?'
        role = (
            "You are operating as a system that, given a list of sentence & aspect term pairs, you will analyze then identify the sentiment & polarity of the aspect term within the context of the given sentence by filling a json array with that data for later parsing."
            "Polarity is either positive (0), negative (1) or neutral (2). Then, determine if the expression is implicit or explicit (True or False)."
            "Return the results as a JSON array with proper formatting, where each entry is a JSON object with two keys:'polarity' and 'implicitness'."
            "Each entry represents an input sentence-aspect pair, indexed accordingly."
            "If an aspect is 'NONE', return an object with the polarity calculated as normal but with the 'implicitness' set to 'False'. eg. [{'polarity': 1, 'implicitness': 'False'}, {'polarity': 0, 'implicitness': 'True'}, ...]"
            "Be sure to assess every single aspect term and that the length of your output is exactly the same as the length of the given sentence array and aspect array."
            "Be sure to check for Trailing Commas, Missing/Extra Brackets, Correct Quotation Marks, Special Characters. Do not add the word 'json' before you give the output!")
        self.polarity_implicitness = self.prompt_gpt(role, prompt)
        try:
            if self.polarity_implicitness is None or self.aspects is None:
                raise TypeError("One or both of the lists are NoneType and cannot be compared.")

            assert len(self.polarity_implicitness) == len(self.aspects), \
                f"Length mismatch: polarity_implicitness ({len(self.polarity_implicitness)}) vs aspects ({len(self.aspects)})"

        except (json.JSONDecodeError, AssertionError, TypeError, ValueError) as e:
            print("Error occurred:", str(e))
        return self.polarity_implicitness

    def transform_df(self, raw_text, token_ids, token_type_ids, attention_masks, aspect_terms, aspect_mask, polarity_implicitness):
        # aspect_terms = [i['aspectTerm'] for i in aspect]
        try:
            implicitness = [self.safe_strtobool(i['implicitness']) for i in polarity_implicitness]
        except:
            print()
        polarity = [i['polarity'] for i in polarity_implicitness]

        rows = [
            Row(
                aspect=aspect_terms[i],
                aspect_mask=aspect_mask[i],
                token_ids=token_ids[i],
                token_type_ids=token_type_ids[i],
                attention_mask=attention_masks[i],
                implicitness=implicitness[i],
                polarity=polarity[i],
                raw_text=raw_text[i]
            )
            for i in range(len(aspect_terms))
        ]
        final_train_df = self.spark_session.createDataFrame(rows, self.isa_schema)

        full_final_df = final_train_df.alias('a').join(
            self.base_df.alias('b'),
            col('a.' + self.out_text_col) == col('b.' + self.raw_text_col),
            "left"
        ).select('b.*', 'a.*')

        full_final_df.show()
        return full_final_df

    def write_parquet_file(self, result_df, parquet_path):
        print('Writing df to Parquet file. See data below.')
        result_df.show()
        if not os.path.exists(parquet_path):
            result_df.write.parquet(parquet_path)
        else:
            result_df.write.mode('append').parquet(parquet_path)

    def write_pkl_file(self, pkl_path):
        result_df = self.spark_session.read.schema(self.final_schema).parquet(f"{self.output_file_path}")
        result_df.printSchema()
        try:
            train_df = result_df.select(col('raw_text').alias('raw_texts'),
                                         col('aspect').alias('raw_aspect_terms'),
                                         col('token_ids').alias('bert_tokens'),
                                         col('aspect_mask').alias('aspect_masks'),
                                         col('implicitness').alias('implicits'),
                                         col('polarity').alias('labels')
                                        # col('token_type_ids').alias('token_type_ids'),
                                        # col('attention_mask').alias('attention_mask'),
            )
            train_df.show()

            data_rows = train_df.collect()
            # data = [row.asDict() for row in train_df.collect()]
            data_dict = {
                'raw_texts': [row['raw_texts'] for row in data_rows],
                'raw_aspect_terms': [row['raw_aspect_terms'] for row in data_rows],
                'bert_tokens': [row['bert_tokens'] for row in data_rows],
                'aspect_masks': [row['aspect_masks'] for row in data_rows],
                'implicits': [row['implicits'] for row in data_rows],
                'labels': [row['labels'] for row in data_rows]
            }

            with open(pkl_path, 'wb') as file:
                pickle.dump(data_dict, file)
                print("Data successfully written to pickle file.")
        except Exception as e:
            print(f"An error occurred: {e}")

    @runtime
    def run(self):
        # remaining_df = self.input_df
        while self.remaining_df.count() > 0:
            self.batch_df = self.remaining_df.limit(self.batch_size)

            # ------------------------------------------
            raw_batch_array = self.batch_df.select(self.raw_text_col).rdd.flatMap(lambda x: x).collect()
            self.batch_extract_aspects(raw_batch_array)
            self.extract_text_tokens(raw_batch_array)
            self.batch_df = self.prep_token_flatten(self.batch_df, raw_batch_array)

            # Bootle Neck
            self.aspects, self.batch_df = self.flatten_df(self.batch_df, raw_batch_array, self.raw_text_col, self.aspects, 'aspectTerm', dict)
            # / Bootle Neck

            self.index = self.batch_df.select('index').rdd.flatMap(lambda x: x).collect()
            raw_text = self.batch_df.select(self.raw_text_col).rdd.flatMap(lambda x: x).collect()
            input_ids = self.batch_df.select("input_ids").rdd.flatMap(lambda x: x).collect()
            token_type_ids = self.batch_df.select("token_type_ids").rdd.flatMap(lambda x: x).collect()
            attention_mask = self.batch_df.select("attention_mask").rdd.flatMap(lambda x: x).collect()

            self.batch_generate_aspect_masks(self.index)
            self.batch_extract_polarity_implicitness(raw_batch_array, self.aspects)

            self.processed_batch_df = self.transform_df(raw_text, input_ids, token_type_ids, attention_mask, self.aspects, self.aspect_masks, self.polarity_implicitness)
            # ------------------------------------------
            self.write_parquet_file(self.processed_batch_df, self.output_file_path)
            self.processed_ids = self.processed_batch_df.select(self.raw_text_col).rdd.flatMap(lambda x: x).collect()
            self.remaining_df = self.remaining_df.filter(~self.remaining_df[self.raw_text_col].isin(self.processed_ids))
            self.remaining_df.show()

        if not os.path.exists(self.output_pkl_path):
            self.write_pkl_file(self.output_pkl_path)
            print('Run Complete.')
        else:
            print('All data already processed. Terminating.')

if __name__ == '__main__':
    raw_file_path = './data/raw/TTCommentExporter-7226101187500723498-201-comments.csv'
    out_parquet_path = "./data/gen/debug_train_dataframe.parquet"
    out_pkl_path = './data/gen/Tiktok_Train_Implicit_Labeled_preprocess_finetune.pkl'

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='./config/genconfig.yaml', help='config file')
    # parser.add_argument('-i', '--raw_file_path', default='/Users/jordanharris/Code/PycharmProjects/THOR-GEN/data/raw/raw_dev.csv')
    parser.add_argument('-r', '--raw_file_path', default=raw_file_path)
    parser.add_argument('-r_col', '--raw_text_col', default='Comment')
    parser.add_argument('-o', '--out_file_path', default=out_parquet_path)
    parser.add_argument('-o_col', '--out_text_col', default='raw_text')

    parser.add_argument('-of', '--output_format', default='pkl', choices=['xml', 'json', 'pkl'])
    parser.add_argument('-pkl', '--output_pkl_path', default=out_pkl_path)

    args = parser.parse_args()
    gen = genDataset(args=args)
    gen.run()
