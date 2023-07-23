import time
import json
import random

from g4f import ChatCompletion, Provider, ModelUtils
from quart import Quart, request
from quart_cors import cors
import nest_asyncio
nest_asyncio.apply()

providers = {
    'gpt-3.5-turbo': Provider.EasyChat,
    'gpt-4': Provider.ChatgptAi,
}

MODEL_IDS = list(ModelUtils.convert.keys())
DEFAULT_MODEL = 'gpt-3.5-turbo'
app = Quart(__name__)
cors(app)


@app.route("/models", methods=['GET'])
def get_models():
    data = [{'id': s} for s in MODEL_IDS]
    return {'data': data}


@app.route("/chat/completions", methods=['POST'])
async def chat_completions():
    data = await request.get_json()
    streaming = data.get('stream', False)
    model = data.get('model', DEFAULT_MODEL)
    messages = data.get('messages')

    if model not in MODEL_IDS:
        model = DEFAULT_MODEL
        
    if model in providers:
        provider = providers[model]
        stream = False if streaming and not provider.supports_stream else streaming
    else:
        stream = streaming
        provider = None

    response = ChatCompletion.create(model=model, stream=stream,
                                     messages=messages, provider=provider)

    if not streaming:
        while 'curl_cffi.requests.errors.RequestsError' in response:
            response = ChatCompletion.create(model=model, stream=stream,
                                             messages=messages, provider=provider)

        completion_timestamp = int(time.time())
        completion_id = ''.join(random.choices(
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=28))

        return {
            'id': 'chatcmpl-%s' % completion_id,
            'object': 'chat.completion',
            'created': completion_timestamp,
            'model': model,
            'usage': {
                'prompt_tokens': None,
                'completion_tokens': None,
                'total_tokens': None
            },
            'choices': [{
                'message': {
                    'role': 'assistant',
                    'content': response
                },
                'finish_reason': 'stop',
                'index': 0
            }]
        }

    def do_stream():
        response_stream = [str(response)] if streaming and not stream else response
        for token in response_stream:
            completion_timestamp = int(time.time())
            completion_id = ''.join(random.choices(
                'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=28))

            completion_data = {
                'id': f'chatcmpl-{completion_id}',
                'object': 'chat.completion.chunk',
                'created': completion_timestamp,
                'model': 'gpt-3.5-turbo-0301',
                'choices': [
                    {
                        'delta': {
                            'content': token
                        },
                        'index': 0,
                        'finish_reason': None
                    }
                ]
            }

            yield 'data: %s\n\n' % json.dumps(completion_data, separators=(',' ':'))
            time.sleep(0.1)

    return app.response_class(do_stream(), mimetype='text/event-stream')


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    host = request.host
    isHuggingface = "hf.space" in host
    protocol = "https" if isHuggingface else request.scheme
    proxy_url = f'{protocol}://{host}'
    return f'<h1>OpenAI Reverse Proxy URL:</h1><h2>{proxy_url}</h2><h1>Models:</h1><h2>{str(list(providers.keys()))}</h2><h3>(Enable "Show "External" models" in ST to see all)</h3>'


if __name__ == '__main__':
    config = {
        'host': '0.0.0.0',
        'port': 80,
        'debug': False
    }

    app.run(**config)
