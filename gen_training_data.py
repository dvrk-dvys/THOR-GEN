import argparse
import math
import pickle
import os
import time
from functools import wraps
from collections import Counter, defaultdict

import yaml
import numpy as np
from collections import Counter
from attrdict import AttrDict

import transformers
from transformers import TFRobertaModel
from transformers import AutoTokenizer
import pandas as pd
import spacy


from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import Row
from pyspark.sql.functions import explode, col, expr, array_join, upper, left, rank
from pyspark.sql.functions import lit, udf, monotonically_increasing_id
from pyspark.sql.functions import unix_timestamp, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, IntegerType, BinaryType, BooleanType, LongType, DoubleType
from openai import OpenAI
import json
from distutils.util import strtobool
from src.utils import prompt_direct_inferring, prompt_direct_inferring_masked, prompt_for_aspect_inferring
import stanza

stanza.download('en')
#doc = nlp("Barack Obama was born in Hawaii.") # run annotation over a sentence

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
            # return none?
            # return None
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
        #self.entropy_udf = udf(lambda text: calculate_shannon_entropy(text), DoubleType())
        #self.entropy_udf = udf(entropy_udf, DoubleType())

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
        self.stanza_file_path = args.stanza_file_path
        self.output_file_path = args.out_file_path
        self.raw_text_col = args.raw_text_col
        self.out_text_col = args.out_text_col
        self.batch_size = self.config['gen_batch_size']
        self.output_pkl_path = args.output_pkl_path

        self.processed_ids = []
        self.remaining_df = None

        self.trigram_probabilities = {}


        self.base_df, self.raw_input_array = self.initialize_df(self.raw_text_col, self.out_text_col)
        self.model = "gpt-4o"
        #self.model = "gpt-4"
        #self.model="gpt-3.5-turbo"
    @staticmethod
    @udf(returnType=DoubleType())
    def calc_shannon_entropy(text):
        tokens = text.split()
        freq_dist = Counter(tokens)
        total_tokens = len(tokens)
        prob_dist = {token: count / total_tokens for token, count in freq_dist.items()}
        entropy = -sum(prob * math.log2(prob) for prob in prob_dist.values())
        return entropy

    def calc_joint_prob_dist(self, corpus):
        tokens = corpus.lower().split()
        total_tokens = len(tokens)
        freq_dist = Counter(tokens)
        prob_dist = {token: count / total_tokens for token, count in freq_dist.items()}
        bigram_freq_dist = Counter(zip(tokens, tokens[1:]))
        joint_prob_dist = {bigram: count / (total_tokens - 1) for bigram, count in bigram_freq_dist.items()}
        return prob_dist, joint_prob_dist

    def construct_reply_trees(self, comment_pairs):
        reply_tree = {}
        for row in comment_pairs:
            comment_id = row["Comment ID"]
            reply_to_id = row["Reply to Which Comment"]
            if reply_to_id:
                if reply_to_id not in reply_tree:
                    reply_tree[reply_to_id] = []
                reply_tree[reply_to_id].append(comment_id)
        return reply_tree

    def calc_trigram_probabilities(self, corpus):
        tokens = corpus.lower().split()
        total_tokens = len(tokens)

        trigram_freq_dist = Counter(zip(tokens, tokens[1:], tokens[2:]))
        bigram_freq_dist = Counter(zip(tokens, tokens[1:]))

        self.trigram_probabilities = {
            (w1, w2, w3): count / bigram_freq_dist[(w1, w2)]
            for (w1, w2, w3), count in trigram_freq_dist.items()
        }

    def calc_contextual_trigram_probabilities(self, corpus):
        tokens = corpus.lower().split()
        total_tokens = len(tokens)

        trigram_freq_dist = Counter(zip(tokens, tokens[1:], tokens[2:]))
        bigram_freq_dist = Counter(zip(tokens, tokens[1:]))

        trigram_probabilities = {
            (w1, w2, w3): count / bigram_freq_dist[(w1, w2)]
            for (w1, w2, w3), count in trigram_freq_dist.items()
        }
        return trigram_probabilities

    def contextual_surprisal(self, text, trigram_probabilities):
        words = text.lower().split()
        surprisals = []

        for i in range(2, len(words)):
            w1, w2, w3 = words[i - 2], words[i - 1], words[i]
            trigram_prob = trigram_probabilities.get((w1, w2, w3), 1e-10)  # Small probability for unseen trigrams
            surprisal = -math.log2(trigram_prob)
            surprisals.append(surprisal)

        return sum(surprisals) / len(surprisals) if surprisals else 0.0

    def contextual_perplexity(self, text, trigram_probabilities):
        words = text.lower().split()
        N = len(words)
        log_prob_sum = 0.0

        for i in range(2, len(words)):
            w1, w2, w3 = words[i - 2], words[i - 1], words[i]
            trigram_prob = trigram_probabilities.get((w1, w2, w3), 1e-10)  # Small probability for unseen trigrams
            log_prob_sum += math.log2(trigram_prob)

        avg_log_prob = log_prob_sum / (N - 2) if N > 2 else 0
        perplexity = 2 ** (-avg_log_prob)
        return perplexity

   #def calculate_tree_prob_dist(self, tree_comments):
   #     tokens = " ".join(tree_comments).lower().split()
   #     total_tokens = len(tokens)
   #     freq_dist = Counter(tokens)
   #     prob_dist = {token: count / total_tokens for token, count in freq_dist.items()}
   #     bigram_freq_dist = Counter(zip(tokens, tokens[1:]))
   #     joint_prob_dist = {bigram: count / (total_tokens - 1) for bigram, count in bigram_freq_dist.items()}
   #     return prob_dist, joint_prob_dist

    def contextual_MI_Score(self, text, prob_dist, joint_prob_dist):
        tokens = text.lower().split()
        mutual_information_score = 0.0
        for i in range(len(tokens) - 1):
            x, y = tokens[i], tokens[i + 1]
            joint_prob = joint_prob_dist.get((x, y), 1e-10)  # Small probability for unseen bigrams
            marginal_prob_x = prob_dist.get(x, 1e-10)
            marginal_prob_y = prob_dist.get(y, 1e-10)
            mutual_information_score += joint_prob * math.log2(joint_prob / (marginal_prob_x * marginal_prob_y))
        return mutual_information_score

    def construct_contextual_scores(self, df):
        comment_pairs = [row.asDict() for row in df.collect()]
        reply_trees = self.construct_reply_trees(comment_pairs)
        scores = []

        for root_comment, comment_ids in reply_trees.items():
            comment_ids = [root_comment] + comment_ids

            branch = df.filter(df["Comment ID"].isin(comment_ids)).select("Comment ID", "Comment").collect()
            comment_corpus = " ".join([row["Comment"] for row in branch])

            prob_dist, joint_prob_dist = self.calc_joint_prob_dist(comment_corpus)
            contextual_trigram_probabilities = self.calc_contextual_trigram_probabilities(comment_corpus)

            for comment_row in branch:
                comment = comment_row["Comment"]
                mi_score = self.contextual_MI_Score(comment, prob_dist, joint_prob_dist)
                surprisal_score = self.contextual_surprisal(comment, contextual_trigram_probabilities)
                perplexity_score = self.contextual_perplexity(comment, contextual_trigram_probabilities)
                scores.append((comment_row["Comment ID"], float(mi_score), float(surprisal_score), float(perplexity_score)))

        scores_df = self.spark_session.createDataFrame(scores, ["Comment ID", "contextual_mutual_information_score", "contextual_surprisal", "contextual_perplexity"])
        df = df.join(scores_df, on="Comment ID", how="left")
        return df

    def initialize_df(self, raw_text_column, out_text_col):
        base_df = (
            self.spark_session.read
            .schema(self.csv_schema)
            .csv(f"{self.input_file_path}", header=True, inferSchema=True)
            .withColumn("shannon_entropy", self.calc_shannon_entropy(col(raw_text_column)))
            #.withColumn("surprisal", self.calculate_surprisal(col(raw_text_column)))
            .withColumn("index", monotonically_increasing_id())
            .withColumn("Comment Time", from_unixtime(unix_timestamp(col("Comment Time"), "dd/MM/yyyy, HH:mm:ss")))
            .orderBy(col("Comment Time"))
            # .limit(self.batch_size)
        )
        base_df.show()
        stanza_df = self.spark_session.read.parquet(self.stanza_file_path)
        joined_df = base_df.join(stanza_df, base_df[raw_text_column] == stanza_df['sentence'], "left_outer")
        base_df = joined_df.drop(stanza_df['sentence'])
        base_df.show()

        #####################

        corpus = base_df.selectExpr("collect_list(Comment) as Comment").collect()[0]["Comment"]
        self.comment_corpus = " ".join(corpus)
        self.calc_trigram_probabilities(self.comment_corpus)
        self.prob_dist, self.joint_prob_dist = self.calc_joint_prob_dist(self.comment_corpus)

        prob_dist_broadcast = self.spark_session.sparkContext.broadcast(self.prob_dist)
        joint_prob_dist_broadcast = self.spark_session.sparkContext.broadcast(self.joint_prob_dist)

        @udf(returnType=DoubleType())
        def mutual_information_udf(text):
            prob_dist = prob_dist_broadcast.value
            joint_prob_dist = joint_prob_dist_broadcast.value
            tokens = text.lower().split()
            mutual_information_score = 0.0
            for i in range(len(tokens) - 1):
                x, y = tokens[i], tokens[i + 1]
                joint_prob = joint_prob_dist.get((x, y), 1e-10)  # Small probability for unseen bigrams
                marginal_prob_x = prob_dist.get(x, 1e-10)
                marginal_prob_y = prob_dist.get(y, 1e-10)
                mutual_information_score += joint_prob * math.log2(joint_prob / (marginal_prob_x * marginal_prob_y))
            return mutual_information_score

        base_df = base_df.withColumn("mutual_information_score", mutual_information_udf(col("Comment")))

        trigram_probabilities_broadcast = self.spark_session.sparkContext.broadcast(self.trigram_probabilities)

        @udf(returnType=DoubleType())
        def surprisal_udf(text):
            trigram_probabilities = trigram_probabilities_broadcast.value
            words = text.lower().split()
            surprisals = []

            for i in range(2, len(words)):
                w1, w2, w3 = words[i - 2], words[i - 1], words[i]
                trigram_prob = trigram_probabilities.get((w1, w2, w3), 1e-10)  # Small probability for unseen trigrams
                surprisal = -math.log2(trigram_prob)
                surprisals.append(surprisal)

            return sum(surprisals) / len(surprisals) if surprisals else 0.0


        base_df = base_df.withColumn("surprisal", surprisal_udf(col("Comment")))
        @udf(returnType=DoubleType())
        def perplexity_udf(text):
            trigram_probabilities = trigram_probabilities_broadcast.value
            words = text.lower().split()
            N = len(words)
            log_prob_sum = 0.0

            for i in range(2, len(words)):
                w1, w2, w3 = words[i - 2], words[i - 1], words[i]
                trigram_prob = trigram_probabilities.get((w1, w2, w3), 1e-10)  # Small probability for unseen trigrams
                log_prob_sum += math.log2(trigram_prob)

            avg_log_prob = log_prob_sum / (N - 2) if N > 2 else 0
            perplexity = 2 ** (-avg_log_prob)
            return perplexity

        base_df = base_df.withColumn("perplexity", perplexity_udf(col("Comment")))

        base_df = self.construct_contextual_scores(base_df)
        base_df.show()



        # base_df = base_df.withColumn("Comment Time", col("Comment Time").cast("timestamp"))
        base_df = base_df.withColumn("Comment Time", from_unixtime(unix_timestamp(col("Comment Time"), "dd/MM/yyyy, HH:mm:ss")))
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
        self.remaining_df.show()
        print(self.remaining_df.count(), ' Rows remaining')
        return self.remaining_df, raw_input_array

    def extract_spaCy_features(self, doc):
        artifacts = {
            'tokens': [],
            'POS_tags': [],
            'dependencies': [],
            'negations': []
        }

        for token in doc:
            artifacts['tokens'].append(token.text)
            artifacts['POS_tags'].append(token.pos_)
            artifacts['dependencies'].append(token.dep_)
            # artifacts['lemmas'].append(token.lemma_)
            # artifacts['heads'].append(token.head.text)
            if token.dep_ == 'neg':
                artifacts['negations'].append(token.head.text)
        # for ent in doc.ents:
        #     artifacts['entities'].append(ent.text)
        #     artifacts['labels'].append(ent.label_)
        # #
        # for span in doc.sents:
        #     artifacts['sentences'].append(span.text)
        return artifacts

    def batch_preprocess_text(self, input_texts):
        self.spaCy_features = {
            'tokens': [],
            'POS_tags': [],
            'dependencies': [],
            'negations': []
        }

        for doc in self.nlp.pipe(input_texts):
            features = self.extract_spaCy_features(doc)
            self.spaCy_features['tokens'].append(features['tokens'])
            self.spaCy_features['POS_tags'].append(features['POS_tags'])
            self.spaCy_features['dependencies'].append(features['dependencies'])
            self.spaCy_features['negations'].append(features['negations'])

        # print("spaCy features extracted:", self.spaCy_features)
        # return self.spaCy_features

    def extract_spaCy_features(self, doc):
         artifacts = [[],[],[],[]]

         for token in doc:
             artifacts[0].append(token.text)  # Append each token's text to the list
             # artifacts['lemmas'].append(token.lemma_)
             artifacts[1].append(token.pos_)
             artifacts[2].append(token.dep_)
             # artifacts['heads'].append(token.head.text)

         # for ent in doc.ents:
         #     artifacts['entities'].append(ent.text)
         #     artifacts['labels'].append(ent.label_)
         #
         # for span in doc.sents:
         #     artifacts['sentences'].append(span.text)

             if token.dep_ == 'neg':
                 artifacts[3].append(token.head.text)

         return artifacts

    # def batch_preprocess_text(self, input_texts):
    #     # self.spaCy_features = []
    #
    #     self.spaCy_features = {
    #         'tokens': [],
    #         # The base form of each word, useful for normalizing text to reduce word form variation and improve matching and retrieval tasks.
    #         # 'lemmas': [],
    #         # Part-of-speech tags for each word, critical for understanding grammatical structure and roles, aiding in parsing and informing syntactic analysis.
    #         'POS_tags': [],
    #         # Dependency relations between tokens, essential for understanding syntactic structure of sentences, which is pivotal in tasks that require deep comprehension of sentence construction.
    #         'dependencies': [],
    #         # The syntactic head of each token, indicating the token that governs or controls the token in syntax, crucial for parsing tree construction and understanding hierarchical syntax relationships.
    #         # 'heads': [],
    #         # # Named entities extracted from text, such as names of people, organizations, locations, etc., key for information extraction and knowledge graph construction.
    #         # 'entities': [],
    #         # # Labels associated with the named entities, indicating the category of each entity (e.g., person, location, organization), useful for classifying and differentiating types of information in text.
    #         # 'labels': [],
    #         # #  Individual sentences segmented from the text, fundamental for tasks that operate on or analyze data at the sentence level, such as summarization or sentiment analysis.
    #         # 'sentences': [],
    #         'negations': []
    #         # 'categories': doc.cats  # Capture categories if available (often empty without training)
    #     }
    #
    #     for doc in self.nlp.pipe(input_texts):
    #         a = self.extract_spaCy_features(doc)
    #         self.spaCy_features['tokens'].append(a[0])  # Append each token's text to the list
    #         # artifacts['lemmas'].append(token.lemma_)
    #         a['POS_tags'].append(a[1])
    #         a['dependencies'].append(a[2])
    #         # artifacts['heads'].append(token.head.text)
    #
    #         # for ent in doc.ents:
    #         #     artifacts['entities'].append(ent.text)
    #         #     artifacts['labels'].append(ent.label_)
    #         #
    #         # for span in doc.sents:
    #         #     artifacts['sentences'].append(span.text)
    #
    #         a['negations'].append(a[3])
    #
    #         # features = self.extract_spaCy_features(doc)
    #         # self.spaCy_features.append(features)
    #
    #     # return self.spaCy_features

    def extract_negations(self, text):
        print()

    def preprocess_text(self, text):
        nlp = stanza.Pipeline('en')
        doc = nlp("Barack Obama was born in Hawaii.")  # run annotation over a sentence
        print()

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
        self.bert_tokens = batch_encoded
        return self.bert_tokens


    def prep_token_flatten(self, batch_df, raw_batch_array):
        zip_data = [
            (input_ids, token_type_ids, attention_mask, spaCy_tokens, POS_tags, dependencies, negations, raw_input)
            for input_ids, token_type_ids, attention_mask, spaCy_tokens, POS_tags, dependencies, negations, raw_input in zip(
                self.bert_tokens.data['input_ids'],
                self.bert_tokens.data['token_type_ids'],
                self.bert_tokens.data['attention_mask'],
                self.spaCy_features['tokens'],
                self.spaCy_features['POS_tags'],
                self.spaCy_features['dependencies'],
                self.spaCy_features['negations'],
                raw_batch_array
            )
        ]

        token_nest_df = self.spark_session.createDataFrame(zip_data, ['input_ids', 'token_type_ids', 'attention_mask', 'spaCy_tokens', 'POS_tags', 'dependencies', 'negations', self.raw_text_col])
        token_nest_df.show()
        batch_df.show()
        batch_df = batch_df.join(token_nest_df, self.raw_text_col, "left").orderBy('index')
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
        response = completion.choices[0].message.content
        try:
            response = json.loads(response)
        except:
            print()
        print(response)
        assert isinstance(response, list), f"{self.model} output is read to list"
        assert isinstance(response[0], dict), f"{self.model} output is read to list"
        return response

    def generate_aspect_mask(self, sentence_tokens, aspect_tokenized):
        try:
            mask = [0] * len(sentence_tokens)
            aspect_len = len(aspect_tokenized)
            for i in range(len(sentence_tokens) - aspect_len + 1):
                if sentence_tokens[i:i + aspect_len] == aspect_tokenized:
                    for j in range(i, i + aspect_len):
                        mask[j] = 1
        except:
            print()
        return mask

    def batch_generate_aspect_masks(self, input_ids, index):
        self.aspect_masks = []
        for i, a in enumerate(self.aspects):
            encoded_aspect_token = self.tokenizer.encode(a, add_special_tokens=False)
            local_index = index[i] % self.batch_size
            self.aspect_masks.append(self.generate_aspect_mask(self.bert_tokens.data['input_ids'][local_index], encoded_aspect_token))
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

    def batch_extract_aspects(self, batch_input_array, batch_spaCy_features):

        new_context = f'Given these sentences "{batch_input_array}" and these spaCy NLP features "{batch_spaCy_features}", '
        prompt = new_context + f'which words or phrases are the aspect terms?'
        role = (
            "You are a system that identifies the core word(s) or phrase(s) in a list of sentences, which represent the aspect or target term(s). "
            "When considering each sentence also assess all of the nlp spaCy features at the corresponding index."
            "The NLP features you will be looking at are the TOKENS, POS TAGS, DEPENDENCIES and NEGATIONS if applicable"
            "Return the results as a JSON array with proper formatting, where each entry is a JSON object with one key:'aspectTerm'."
            "If a sentence contains more than one aspect term, list them together as the value for 'aspectTerm'. For example, [{'aspectTerm': 'term0'}, {'aspectTerm': ['term0', 'term1', 'term2']}, ...]."
            "If not significant aspect term is found have the value be 'NONE'. Each aspect object corresponds to the input sentence, indexed accordingly."
            "Finally check your output for trailing commas, missing or extra brackets, correct quotation marks, and special characters."
            "Ensure the output contains only this JSON array and no additional text."
        )
        self.aspects = self.prompt_gpt(role, prompt)
        try:
            assert len(self.aspects) == len(batch_input_array)
        except:
            print()
        #assert len(self.aspects) == len(batch_input_array)
        return self.aspects  #, self.aspect_masks

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
    def batch_extract_polarity_implicitness(self, batch_input_array, batch_spaCy_features, aspects):
        new_context = f'Given these sentences "{batch_input_array}", spaCy NLP features "{batch_spaCy_features} and corresponding aspect terms "{aspects}" with input length: {len(aspects)}, '
        # new_context = f'Given this list of lists of sentences, spaCy NLP features and corresponding aspect terms "{zipped_data}" of  length: {self.batch_size}, '
        prompt = new_context + f'determine the polarity (positive, negative or neutral) of aspect term and if it is explicitly or implicitly expressed with respect to the whole sentence?'
        role = (
            "You are operating as a system that, given a list of sentence, spaCy NLP features & aspect terms, you will analyze then identify the sentiment & polarity of the aspect term within the context of the given sentence."
            "When considering each sentence also assess all of the nlp spaCy features at the corresponding index."
            "The NLP features you will be looking at are the TOKENS, POS TAGS, DEPENDENCIES and NEGATIONS if applicable"
            "Polarity is either positive (0), negative (1) or neutral (2). Then, determine if the expression is implicit or explicit (True or False)."
            "Return the results as a JSON array with proper formatting, where each entry is a JSON object with two keys:'polarity' and 'implicitness'."
            "Each entry represents an input sentence-feature-aspect set, indexed accordingly."
            "If an aspect is 'NONE', return an object with the polarity calculated as normal but with the 'implicitness' set to 'False'. eg. [{'polarity': 1, 'implicitness': 'False'}, {'polarity': 0, 'implicitness': 'True'}, ...]"
            "Be sure to assess every single aspect term and that the length of your output is EXACTLY THE SAME as the length as the INPUT."
            "Be sure to check for Trailing Commas, Missing/Extra Brackets, Correct Quotation Marks, Special Characters."
            "Ensure the output contains only this JSON array and no additional text.")
        self.polarity_implicitness = self.prompt_gpt(role, prompt)
        try:
            assert len(self.polarity_implicitness) == len(aspects)
        except:
            print()
        return self.polarity_implicitness

    def transform_df(self, raw_text, token_ids, token_type_ids, attention_masks, aspect_terms, aspect_mask, polarity_implicitness):
        # aspect_terms = [i['aspectTerm'] for i in aspect]

        implicitness = [self.safe_strtobool(i['implicitness']) for i in polarity_implicitness]
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
        # try:
        final_train_df = self.spark_session.createDataFrame(rows, self.isa_schema)
        # except:
        #     print()

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
            self.batch_preprocess_text(raw_batch_array)
            self.extract_text_tokens(raw_batch_array)

            # print("SpaCy Tokens:", self.spaCy_features[0]['tokens'])
            # print("BERT Tokens:", self.bert_tokens.data['input_ids'][0])
            # print()
            self.batch_extract_aspects(raw_batch_array, self.spaCy_features)
            self.batch_df = self.prep_token_flatten(self.batch_df, raw_batch_array)

            # Bootle Neck
            self.aspects, self.batch_df = self.flatten_df(self.batch_df, raw_batch_array, self.raw_text_col, self.aspects, 'aspectTerm', dict)
            # / Bootle Neck

            self.index = self.batch_df.select('index').rdd.flatMap(lambda x: x).collect()
            raw_text = self.batch_df.select(self.raw_text_col).rdd.flatMap(lambda x: x).collect()
            input_ids = self.batch_df.select("input_ids").rdd.flatMap(lambda x: x).collect()
            token_type_ids = self.batch_df.select("token_type_ids").rdd.flatMap(lambda x: x).collect()
            attention_mask = self.batch_df.select("attention_mask").rdd.flatMap(lambda x: x).collect()
            spaCy_tokens = self.batch_df.select("spaCy_tokens").rdd.flatMap(lambda x: x).collect()
            POS_tags = self.batch_df.select("POS_tags").rdd.flatMap(lambda x: x).collect()
            dependencies = self.batch_df.select("dependencies").rdd.flatMap(lambda x: x).collect()
            negations = self.batch_df.select("negations").rdd.flatMap(lambda x: x).collect()


            self.batch_generate_aspect_masks(input_ids, self.index)
            batch_spaCy_features = [spaCy_tokens, POS_tags, dependencies, negations]
            self.batch_extract_polarity_implicitness(raw_batch_array, batch_spaCy_features, self.aspects)

            self.processed_batch_df = self.transform_df(raw_text, input_ids, token_type_ids, attention_mask, self.aspects, self.aspect_masks, self.polarity_implicitness)
            # ------------------------------------------
            self.write_parquet_file(self.processed_batch_df, self.output_file_path)
            self.processed_ids = self.processed_batch_df.select(self.raw_text_col).rdd.flatMap(lambda x: x).collect()
            self.remaining_df = self.remaining_df.filter(~self.remaining_df[self.raw_text_col].isin(self.processed_ids))
            self.remaining_df.show()
        try:
            self.write_pkl_file(self.processed_batch_df, self.output_pkl_path)
            print('Run Complete.')
        except:
            print('All data already processed. Terminating.')

if __name__ == '__main__':
    raw_file_path = './data/raw/TTCommentExporter-7226101187500723498-201-comments.csv'
    stanza_path = "./data/gen/stanza-7226101187500723498-201.parquet"
    out_parquet_path = "data/gen/train_dataframe.parquet"
    out_pkl_path = './data/gen/Tiktok_Train_Implicit_Labeled_preprocess_finetune.pkl'


    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='./config/genconfig.yaml', help='config file')
    # parser.add_argument('-i', '--raw_file_path', default='/Users/jordanharris/Code/PycharmProjects/THOR-GEN/data/raw/raw_dev.csv')
    parser.add_argument('-r', '--raw_file_path', default=raw_file_path)
    parser.add_argument('-s', '--stanza_file_path', default=stanza_path)

    parser.add_argument('-r_col', '--raw_text_col', default='Comment')
    parser.add_argument('-o', '--out_file_path', default=out_parquet_path)
    parser.add_argument('-o_col', '--out_text_col', default='raw_text')

    parser.add_argument('-of', '--output_format', default='pkl', choices=['xml', 'json', 'pkl'])
    parser.add_argument('-pkl', '--output_pkl_path', default=out_pkl_path)

    args = parser.parse_args()
    gen = genDataset(args=args)
    gen.run()
    #gen.write_pkl_file(out_pkl_path)
