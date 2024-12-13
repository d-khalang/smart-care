
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from config import Config, MyLogger
from manager import DataManager


class TeleBot():
    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.get_main_loggger()
        self.token = self.config.BOT_TOKEN
        self.bot_manager = DataManager(config=config)
        self.ownership_dict = {}
        self.avaiable_plants = []
        self.user_states = {}  # To keep track of user state
        

        self.logger.info("Initiating the Telegram bot...")
        self.bot = telepot.Bot(self.token)
        callback_dict = {'chat': self.on_chat_message,
                         'callback_query': self.on_callback_query}
        MessageLoop(self.bot, callback_dict).run_as_thread()


    def update_ownership(self):
        self.ownership_dict, self.avaiable_plants = self.bot_manager.update_ownership()

    def own_plant(self, plant_id, username, password, telegram_id):
        return self.bot_manager.post_user(plant_id, username, password, telegram_id)
        

    # Triggered when recieving text messages
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        cmd = msg['text']

        if chat_id in self.user_states:
            state = self.user_states[chat_id]
            if state == 'waiting_for_username':
                self.user_states[chat_id] = {'state': 'waiting_for_password', 'plant_id': state['plant_id'], 'username': cmd}
                self.bot.sendMessage(chat_id, "Insert your password:")
            elif state['state'] == 'waiting_for_password':
                plant_id = state['plant_id']
                username = state['username']
                password = cmd
                if self.own_plant(plant_id, username, password, chat_id):
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text='Track your plant', callback_data='Track your plant'),
                         InlineKeyboardButton(text='withdraw the plant', callback_data=f'withdraw plant{plant_id}')]
                    ])
                    self.bot.sendMessage(chat_id, "Congrats!! It's now yours :)", reply_markup=keyboard)
                else:
                    self.bot.sendMessage(chat_id, "Failed to own the plant. Please try again.")
                del self.user_states[chat_id]
        else:
            if cmd == "/start":
                self.bot.sendMessage(chat_id, "Wellcome to smart care bot")

            elif cmd == "/menu":
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Track your plant', callback_data='Track your plant'),
                        InlineKeyboardButton(text='Get a plant', callback_data='Get a plant')]
                ])

                self.bot.sendMessage(chat_id, "You own a plant or need a new one?", reply_markup=keyboard)
            else:
                self.bot.sendMessage(chat_id, "Sorry, I couldn't help you with that!!")


    def on_callback_query(self, msg):
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        self.logger.info(f"query: {str(query_id)} from:{str(from_id)} with content:{str(query_data)}")

        if query_data == "Get a plant":
            self.update_ownership()
            if not self.avaiable_plants:
                self.bot.sendMessage(from_id, "Ops! No plant available :(")
            
            else:
                my_inline_keyboard = []
                for plant_id in self.avaiable_plants:
                    my_inline_keyboard.append([InlineKeyboardButton(text=f'plant {plant_id}', callback_data=f"get{plant_id}")])
    
                keyboard2 = InlineKeyboardMarkup(inline_keyboard=my_inline_keyboard)

                self.bot.sendMessage(from_id, "Available plants:", reply_markup=keyboard2)

        # When getting a plant button is triggered
        elif query_data.startswith('get'):
            plant_id = query_data[3:]
            self.user_states[from_id] = {'state': 'waiting_for_username', 'plant_id': plant_id}
            self.bot.sendMessage(from_id, f"Insert your username for plant {plant_id}:")


        elif query_data.startswith('withraw plant'):
            plant_id = query_data[13:]
            self.user_states[from_id] = {'state': 'waiting_for_username', 'plant_id': plant_id}
            if self.delete_plant_from_users_inventory():
                self.bot.sendMessage(from_id, f"Sorry for your loss of plant {plant_id} :(")
            else:
                self.bot.sendMessage(from_id, "Failed to delete the plant from your inventory. Please try again.")




        elif query_data == "Track your plant":
            if str(from_id) in self.ownershipDict.keys():
                self.bot.sendMessage(from_id, "Your plant information:")

                # get info to show how many days remain until harvesting
                dayUntilReady = self.bot_manager.get_plant_age(self.ownershipDict[str(from_id)])
                self.bot.sendMessage(from_id, f"Your plant will be ready to harvest in {str(dayUntilReady)} days")

                sensingData = self.bot_manager.get_sensors_data(self.ownershipDict[str(from_id)])
                # Convert the dictionary into a string format
                sensing_data_str = "\n".join([f"{sensor_kind}: {value}" for sensor_kind, value in sensingData.items()])
                self.bot.sendMessage(from_id, sensing_data_str)
                
                statusData = self.bot_manager.get_actuators_status(self.ownershipDict[str(from_id)])
                # Convert the dictionary into a string format
                status_data_str = "\n".join([f"{deviceName}: {status}" for deviceName, status in statusData.items()])
                self.bot.sendMessage(from_id, status_data_str)
            
            else:
                self.bot.sendMessage(from_id, "Sorry, you don't have any plant :(")

