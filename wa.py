from flask import Flask, request, jsonify
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import os
from dotenv import load_dotenv
import openai

load_dotenv()

app = Flask(__name__)

ADMIN_NUMBER = ''
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
    headers = {
        'Authorization': f"Bearer {os.getenv('TOKEN')}"
    }
    url = f"{os.getenv('API_URL')}/{endpoint}"
    if params:
        if 'media' in params:
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
    print('Whapi response:', response.json())
    return response.json()

def set_hook():
    if os.getenv('BOT_URL'):
        settings = {
            'webhooks': [
                {
                    'url': os.getenv('BOT_URL'),
                    'events': [{'type': "messages", 'method': "post"}],
                    'mode': "method"
                }
            ]
        }
        send_whapi_request('settings', settings, 'PATCH')

def ask_openai(prompt):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
    model="gpt-4-turbo",  # Use same model
    messages=[
        {"role": "system", "content": "You are ChatGPT, a helpful assistant."},  # Emulate system prompt
        {"role": "user", "content": prompt}
    ],
    max_tokens=2000,
    temperature=0.7,
)
    return response.choices[0].message.content.strip()

@app.route('/hook/messages', methods=['POST'])
def handle_new_messages():
    try:
        messages = request.json.get('messages', [])
        endpoint = None

        for message in messages:
            if message.get('from_me'):
                continue

            sender = {'to': message.get('chat_id')}
            command_input = message.get('text', {}).get('body', '').strip()

            print(f"Received: {command_input} from {sender['to']}")

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

            elif command_input == '12':
                sender['body'] = (
                    "*12. Pengajuan Dokumen*\n\n"
                    "Silakan unggah dokumen Anda ke link berikut:\n"
                    "https://form.jotform.com/\n\n"
                    "Setelah dokumen diunggah, admin akan segera dihubungi."
                )
                endpoint = 'messages/text'

                notify_admin = {
                    'to': ADMIN_NUMBER,
                    'body': f"📩 Pengguna {sender['to']} mengajukan Dokumen. Periksa dokumen yang diunggah."
                }
                send_whapi_request('messages/text', notify_admin)

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
                ) + "\n\nKetik nomor (tanpa titik dan koma) untuk melihat info lebih lanjut. Untuk bertanya dengan Ai, ketik */Ai (pertanyaan yang diajukan)*"
                endpoint = 'messages/text'

            else:
                sender['body'] = "📌 *Daftar FAQ*\n\n" + '\n'.join(
                    f"{key}. {value[0]}" for key, value in COMMANDS.items()
                ) + "\n\nKetik nomor (tanpa titik dan koma) untuk melihat info lebih lanjut. Untuk bertanya dengan Ai, ketik */Ai (pertanyaan yang diajukan)*"
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
    return 'Bot is running'

if __name__ == '__main__':
    set_hook()
    port = os.getenv('PORT') or (443 if os.getenv('BOT_URL', '').startswith('https:') else 80)
    app.run(port=port, debug=True)
