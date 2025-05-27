import logging
import configparser
from telethon import TelegramClient, events

class TelegramSignalListener:
    def __init__(self, config_path, signal_handler):
        """
        :param config_path: шлях до config.ini
        :param signal_handler: функція-обробник сигналів (callable)
        """
        config = configparser.ConfigParser()
        config.read(config_path)
        tg_cfg = config['TRADINGRUHAL_TELEGRAM']

        self.api_id = int(tg_cfg['api_id'])
        self.api_hash = tg_cfg['api_hash']
        self.session_name = tg_cfg['session']
        # Канал вказується як username (через @) або id
        self.channels = [c.strip() for c in tg_cfg['channels'].split(',')]
        self.signal_handler = signal_handler
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

    async def start(self):
        @self.client.on(events.NewMessage(chats=self.channels))
        async def handler(event):
            msg = event.raw_text
            logging.info(f"Отримано сигнал з Telegram: {msg}")
            self.signal_handler(msg)

        await self.client.start()
        logging.info("TelegramSignalListener запущено")
        await self.client.run_until_disconnected()

