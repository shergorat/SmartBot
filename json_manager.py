import json
import logging
import os

data_dir = os.path.join(os.path.dirname(__file__), 'data')
texts_json_path = os.path.join(data_dir, 'texts.json')


def load_texts():
    try:
        with open(texts_json_path, 'r', encoding='utf-8') as json_file:
            custom_texts = json.load(json_file)
    except FileNotFoundError:
        custom_texts = {}
    return custom_texts


def save_texts(custom_texts):
    with open(texts_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(custom_texts, json_file, ensure_ascii=False, indent=4)


custom_texts = load_texts()

api_model_json_path = os.path.join(data_dir, 'openaimodel.json')


def load_api_model() -> dict:
    api_engine_model: dict = {}
    try:
        with open(api_model_json_path, 'r', encoding='utf-8') as json_file:
            api_engine_model = json.load(json_file)
            return api_engine_model
    except FileNotFoundError:
        logging.error(f'File {api_model_json_path} not found')
        raise ValueError(
            f'File {api_model_json_path} not found. '
        )


def save_api_model(api_engine_model):
    with open(api_model_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(api_engine_model, json_file, ensure_ascii=False, indent=4)


api_model = load_api_model()
