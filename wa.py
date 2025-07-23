from flask import Flask, request, jsonify
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import os
from dotenv import load_dotenv
import openai


load_dotenv()  

app = Flask(__name__)


COMMANDS = {
    '1': ('text', 'https://www.google.com', 'text', 'https://www.facebook.com'),
  }



FILES = {
    'IMAGE': './files/file_example_JPG_100kB.jpg',
    'DOCUMENT': './files/file-example_PDF_500_kB.pdf',
    'VIDEO': './files/file_example_MP4_480_1_5MG.mp4',
    'VCARD': './files/sample-vcard.txt'
}


def send_whapi_request(endpoint, params=None, method='POST'):
    """
    Send a request to the Whapi.Cloud API.
    Handles both JSON and multipart (media) requests.
    """
    headers = {
        'Authorization': f"Bearer {os.getenv('TOKEN')}"
    }
    url = f"{os.getenv('API_URL')}/{endpoint}"
    if params:
        if 'media' in params:
            # Handle file upload for media messages
            details = params.pop('media').split(';')
            with open(details[0], 'rb') as file:
                m = MultipartEncoder(fields={**params, 'media': (details[0], file, details[1])})
                headers['Content-Type'] = m.content_type
                response = requests.request(method, url, data=m, headers=headers)
        elif method == 'GET':
            response = requests.get(url, params=params, headers=headers)
        else:
            headers['Content-Type'] = 'application/json'
            response = requests.request(method, url, json=params, headers=headers)
    else:
        response = requests.request(method, url, headers=headers)
    print('Whapi response:', response.json())  # Debug output
    return response.json()


def set_hook():
    """
    Register webhook URL with Whapi.Cloud if BOT_URL is set.
    """
    if os.getenv('BOT_URL'):
        settings = {
            'webhooks': [
                {
                    'url': os.getenv('BOT_URL'),
                    'events': [
                        {'type': "messages", 'method': "post"}
                    ],
                    'mode': "method"
                }
            ]
        }
        send_whapi_request('settings', settings, 'PATCH')


def ask_openai(prompt):
    """
    Send a prompt to OpenAI ChatGPT and return the response.
    """
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


@app.route('/hook/messages', methods=['POST'])
def handle_new_messages():
    try:
        messages = request.json.get('messages', [])
        endpoint = None

        for message in messages:
            if message.get('from_me'):
                continue  # Ignore messages sent by the bot itself

            sender = {'to': message.get('chat_id')}
            command_input = message.get('text', {}).get('body', '').strip()

            if command_input.lower().startswith('/ai '):
                user_prompt = command_input[4:].strip()
                if not user_prompt:
                    sender['body'] = 'Please provide a prompt after /AI.'
                else:
                    try:
                        ai_response = ask_openai(user_prompt)
                        sender['body'] = ai_response
                    except Exception as e:
                        sender['body'] = f"OpenAI error: {e}"
                endpoint = 'messages/text'

            elif command_input in COMMANDS:
                entry = COMMANDS[command_input]
                title = entry[0]
                link1 = entry[1]
                body = f"*{title}*\n{link1}"

                if len(entry) >= 4:
                    label2 = entry[2]
                    link2 = entry[3]
                    body += f"\n\n*{label2}*\n{link2}"

                body += "\n\nKetik *menu* untuk kembali ke daftar FAQ."
                sender['body'] = body
                endpoint = 'messages/text'

            elif command_input.lower() == 'menu':
                sender['body'] = "📌 *Daftar FAQ*\n\n" + '\n'.join(
                    f"{key}. {value[0]}" for key, value in COMMANDS.items()
                ) + "\n\nKetik nomor (tanpa titik dan koma) untuk melihat info lebih lanjut."
                endpoint = 'messages/text'

            else:
                sender['body'] = "📌 *Daftar FAQ*\n\n" + '\n'.join(
                    f"{key}. {value[0]}" for key, value in COMMANDS.items()
                ) + "\n\nKetik nomor (tanpa titik dan koma) untuk melihat info lebih lanjut."
                endpoint = 'messages/text'

            if endpoint:
                response = send_whapi_request(endpoint, sender)
                print(f"Response from Whapi: {response}")

        return 'Ok', 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return str(e), 500



@app.route('/', methods=['GET'])
def index():
    """
    Health check endpoint.
    """
    return 'Bot is running'


if __name__ == '__main__':
    set_hook() 
    port = os.getenv('PORT') or (443 if os.getenv('BOT_URL', '').startswith('https:') else 80)
    app.run(port=port, debug=True)
