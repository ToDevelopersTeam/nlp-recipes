# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""
    Utility functions for downloading, extracting, and reading the
    BBC Hindi News Corpus.
    https://github.com/NirantK/hindi2vec/releases/tag/bbc-hindi-v0.1
"""

import os
import pandas as pd
import logging
import numpy as np
import tarfile

from tempfile import TemporaryDirectory
from utils_nlp.dataset.url_utils import maybe_download
from utils_nlp.models.transformers.common import MAX_SEQ_LEN
from utils_nlp.models.transformers.sequence_classification import Processor
from sklearn.preprocessing import LabelEncoder


URL = (
    "https://github.com/NirantK/hindi2vec/releases/"
    "download/bbc-hindi-v0.1/bbc-hindiv01.tar.gz"
)


def load_pandas_df(local_cache_path='.'):
    """
    Downloads and extracts the dataset files

    Args:
        local_cache_path ([type], optional): [description]. Defaults to None.
        num_rows (int): Number of rows to load. If None, all data is loaded.
    Returns:
        pd.DataFrame: pandas DataFrame containing the loaded dataset.
    """

    zipped_file = URL.split("/")[-1]
    maybe_download(URL, zipped_file, local_cache_path)

    zipped_file_path = os.path.join(local_cache_path, zipped_file)
    tar = tarfile.open(zipped_file_path, "r:gz")
    tar.extractall(path=local_cache_path)
    tar.close()

    train_csv_file_path = os.path.join(local_cache_path, "hindi-train.csv")
    test_csv_file_path = os.path.join(local_cache_path, "hindi-test.csv")

    train_df = pd.read_csv(
        train_csv_file_path,
        sep="\t",
        encoding='utf-8',
        header=None
    )

    test_df = pd.read_csv(
        test_csv_file_path,
        sep="\t",
        encoding='utf-8',
        header=None
    )

    return (train_df, test_df)


def load_dataset(
    local_path=TemporaryDirectory().name,
    test_fraction=1.0,
    random_seed=None,
    train_sample_ratio=1.0,
    test_sample_ratio=1.0,
    model_name="bert-base-uncased",
    to_lower=True,
    cache_dir=TemporaryDirectory().name,
    max_len=MAX_SEQ_LEN
):
    """
    Load the multinli dataset and split into training and testing datasets.
    The datasets are preprocessed and can be used to train a NER model or evaluate
    on the testing dataset.

    Args:
        local_path (str, optional): The local file path to save the raw wikigold file.
            Defautls to TemporaryDirectory().name.
        test_fraction (float, optional): The fraction of testing dataset when splitting.
            This variable is just a placeholder for a unified interface since the BBC Hindi 
            dataset already split training and testing for us. 
            Defaults to 1.0.
        random_seed (float, optional): Random seed used to shuffle the data.
            Defaults to None.
        train_sample_ratio (float, optional): The ratio that used to sub-sampling for training.
            Defaults to 1.0.
        test_sample_ratio (float, optional): The ratio that used to sub-sampling for testing.
            Defaults to 1.0.
        model_name (str, optional): The pretained model name.
            Defaults to "bert-base-uncased".
        to_lower (bool, optional): Lower case text input.
            Defaults to True.
        cache_dir (str, optional): The default folder for saving cache files.
            Defaults to TemporaryDirectory().name.
        max_len (int, optional): Maximum length of the list of tokens. Lists longer
            than this are truncated and shorter ones are padded with "O"s. 
            Default value is BERT_MAX_LEN=512.

    Returns:
        tuple. The tuple contains three elements:
        train_dataset (TensorDataset): A TensorDataset containing the following four tensors.
            1. input_ids_all: Tensor. Each sublist contains numerical values,
                i.e. token ids, corresponding to the tokens in the input 
                text data.
            2. input_mask_all: Tensor. Each sublist contains the attention
                mask of the input token id list, 1 for input tokens and 0 for
                padded tokens, so that padded tokens are not attended to.
            4. label_ids_all: Tensor, each sublist contains token labels of
                a input sentence/paragraph, if labels is provided. If the
                `labels` argument is not provided, it will not return this tensor.

        test_dataset (TensorDataset): A TensorDataset containing the following four tensors.
            1. input_ids_all: Tensor. Each sublist contains numerical values,
                i.e. token ids, corresponding to the tokens in the input 
                text data.
            2. input_mask_all: Tensor. Each sublist contains the attention
                mask of the input token id list, 1 for input tokens and 0 for
                padded tokens, so that padded tokens are not attended to.
            4. label_ids_all: Tensor, each sublist contains token labels of
                a input sentence/paragraph, if labels is provided. If the
                `labels` argument is not provided, it will not return this tensor.
        
        label_encoder (LabelEncoder): a sklearn LabelEncoder instance. The label values
            can be retrieved by calling the `inverse_transform` function.
    """

    # download and load the original dataset
    train_df, test_df = load_pandas_df(local_cache_path=local_path)

    # encode labels, use the "genre" column as the label column
    label_encoder = LabelEncoder()
    label_encoder.fit(train_df[0])

    if train_sample_ratio > 1.0:
        train_sample_ratio = 1.0
        logging.warning("Setting the training sample ratio to 1.0")
    elif train_sample_ratio < 0:
        logging.error("Invalid training sample ration: {}".format(train_sample_ratio))
        raise ValueError("Invalid training sample ration: {}".format(train_sample_ratio))
    
    if test_sample_ratio > 1.0:
        test_sample_ratio = 1.0
        logging.warning("Setting the testing sample ratio to 1.0")
    elif test_sample_ratio < 0:
        logging.error("Invalid testing sample ration: {}".format(test_sample_ratio))
        raise ValueError("Invalid testing sample ration: {}".format(test_sample_ratio))

    if train_sample_ratio < 1.0:
        train_df = train_df.sample(frac=train_sample_ratio).reset_index(drop=True)
    if test_sample_ratio < 1.0:
        test_df = test_df.sample(frac=test_sample_ratio).reset_index(drop=True)

    train_labels = label_encoder.transform(train_df[0])
    test_labels = label_encoder.transform(test_df[0])

    processor = Processor(model_name=model_name, to_lower=to_lower, cache_dir=cache_dir)

    train_dataset = processor.preprocess(
        text=train_df[1],
        labels=train_labels,
        max_len=max_len
    )

    test_dataset = processor.preprocess(
        text=test_df[1],
        labels=test_labels,
        max_len=max_len
    )

    return (train_dataset, test_dataset, label_encoder)


def get_label_values(label_encoder, label_ids):
    """
    Get the label values from label IDs. 

    Args:
        label_encoder (LabelEncoder): a fitted sklearn LabelEncoder instance
        label_ids (Numpy array): a Numpy array of label IDs.

    Returns:
        Numpy array. A Numpy array of label values.
    """

    return label_encoder.inverse_transform(label_ids)