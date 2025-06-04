from binance.client import Client

api_key = "d819d92b03fa3d8c61ff4c4835908ec4afde53fc64ac6df6235c5b332fbef930"
api_secret = "007055837e544dfb38e99582a2b00626164602a168aa939eb5943adb293bf727"
client = Client(api_key, api_secret, testnet=True)

try:
    info = client.futures_account()
    print("SUCCESS! Account info:")
    print(info)
except Exception as e:
    print("ERROR:")
    print(e)
