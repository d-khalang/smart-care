import time
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from config import Config, MyLogger
from manager import DataManager


class TeleBot():
    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.get_main_loggger()
        self.bot_manager = DataManager(config=config)
        token = self.bot_manager.get_bot_token()
        self.token = token
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
    
    def delete_plant_from_user_inventory(self, plant_id, user_id):
        return self.bot_manager.delete_plant_from_user_inventory(plant_id, user_id)
    
    def find_plants_for_username(self, username):
        user_ownership_detail = {}
        for plant_id, user in self.ownership_dict.items():
            if user.get("userName") == username:
                user_ownership_detail[plant_id] = user
        return user_ownership_detail
        
    def show_plant_age(self, plant_id):
        return self.bot_manager.get_plant_age(plant_id)

    def show_sensing_data(self, plant_id):
        return self.bot_manager.get_sensing_data(plant_id)

    def show_actuators_status(self, plant_id):
        return self.bot_manager.show_actuators_status(plant_id)
    
    def get_report(self, plant_id):
        return self.bot_manager.get_report(plant_id)




    # Triggered when recieving text messages
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        cmd = msg['text']

        
        if cmd == "/start":
            self.bot.sendMessage(chat_id, "Wellcome to smart care bot")

        elif cmd == "/menu":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Track your plant', callback_data='Track your plant'),
                    InlineKeyboardButton(text='Get a plant', callback_data='Get a plant')]
            ])

            self.bot.sendMessage(chat_id, "You own a plant or need a new one?", reply_markup=keyboard)
        

        else:
            if chat_id in self.user_states:
                state = self.user_states[chat_id]
                if state['state'] == 'waiting_for_username':
                    self.user_states[chat_id].update({'state': 'waiting_for_password', 'plant_id': state['plant_id'], 'username': cmd})
                    self.bot.sendMessage(chat_id, "Insert your password:")
                elif state['state'] == 'waiting_for_password':
                    plant_id = state['plant_id']
                    username = state['username']
                    password = cmd
                    if self.own_plant(plant_id, username, password, chat_id):
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text='Track your plant', callback_data='Track your plant'),
                            InlineKeyboardButton(text='withdraw the plant', callback_data=f'withdraw_plant{plant_id}')]
                        ])
                        self.bot.sendMessage(chat_id, "Congrats!! It's now yours :)", reply_markup=keyboard)
                    else:
                        self.bot.sendMessage(chat_id, "Failed to own the plant. Please try again.")
                    del self.user_states[chat_id]
                

                elif state['state'] == 'waiting_for_username_to_track_plant':
                    username = cmd
                    user_ownership = self.find_plants_for_username(username=username)
                    if not user_ownership:
                        self.bot.sendMessage(chat_id, "Sorry but you've got no plants :(")
                        del self.user_states[chat_id]
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text='Get a plant', callback_data='Get a plant')]])

                        self.bot.sendMessage(chat_id, 'Don"t worry, you can get one!', reply_markup=keyboard)
                    else:
                        my_inline_keyboard = []
                        self.user_states.update({'state': 'waiting_for_authentication_to_track_plant', 'user_ownership': user_ownership})
                        for plant_id in user_ownership:
                            my_inline_keyboard.append([InlineKeyboardButton(text=f'plant {plant_id}', callback_data=f"track{plant_id}")])
                        keyboard2 = InlineKeyboardMarkup(inline_keyboard=my_inline_keyboard)
                        self.bot.sendMessage(chat_id, "Your plant inventory, choose one to track:", reply_markup=keyboard2)

                elif state['state'] == 'waiting_for_password_to_track_plant':
                    password = cmd
                    plant_id = state['plant_id']
                    user_ownership = self.user_states.get('user_ownership')
                    for user in user_ownership.values():
                        if user.get("password") == password:
                            self.bot.sendMessage(chat_id, f"Authentication passed.")
                            self.show_plant(chat_id, plant_id)
                            del self.user_states[chat_id]

                    if not user_ownership:
                        self.bot.sendMessage(chat_id, "Redo your process from the beginning ")
                        del self.user_states[chat_id]
                else:    
                    self.bot.sendMessage(chat_id, "Redo your process from the beginning ")
                    del self.user_states[chat_id]
            
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


        elif query_data.startswith('withdraw_plant'):
            plant_id = query_data[14:]
            self.user_states[from_id] = {'state': 'waiting_for_username', 'plant_id': plant_id}
            if self.delete_plant_from_user_inventory(plant_id, from_id):
                self.bot.sendMessage(from_id, f"Sorry for your loss of plant {plant_id} :(")
            else:
                self.bot.sendMessage(from_id, "Failed to delete the plant from your inventory. Please try again.")
        
        elif query_data == "Track your plant":
            self.update_ownership()
            self.user_states[from_id] = {'state': 'waiting_for_username_to_track_plant'}
            self.bot.sendMessage(from_id, f"Insert your username: ")

        elif query_data.startswith('track'):
            plant_id = query_data[5:]
            user_ownership = self.user_states.get('user_ownership')
            if not user_ownership:
                self.bot.sendMessage(from_id, "Redo your process from the beginning ")
            else:
                for plant, user in user_ownership.items():
                    if str(plant_id) == str(plant):
                        if str(user.get('telegramId')) == str(from_id):
                            self.bot.sendMessage(from_id, f"Authentication passed by telegram ID.")
                            self.show_plant(from_id, int(plant_id))
                            del self.user_states[from_id]

                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text='Generate Reoprt', callback_data=f'report{plant_id}')]])

                            self.bot.sendMessage(from_id, 'Get your plant"s report!', reply_markup=keyboard)

                        else:
                            user_ownership = {plant: user}
                            self.user_states[from_id].update({'state': 'waiting_for_password_to_track_plant', 'user_ownership': user_ownership,'plant_id': plant_id})
                            self.bot.sendMessage(from_id, f"Insert your password: ")

        elif query_data.startswith('report'):
            self.bot.sendMessage(from_id, "One moment please, working on it :)")
            plant_id = int(query_data[6:]) 
            report_path = self.get_report(plant_id)
            if report_path:
                self.send_pdf(from_id, report_path)
            else:
                self.bot.sendMessage(from_id, "Failed to generate the report :( try again please!")

        else:
            self.bot.sendMessage(from_id, "Something unexpected happend!")


    def show_plant(self, user_id, plant_id):
        self.bot.sendMessage(user_id, "Your plant information:")

        # get info to show how many days remain until harvesting
        day_until_ready = self.show_plant_age(plant_id)
        self.bot.sendMessage(user_id, f"Your plant will be ready to harvest in {str(day_until_ready)} days")

        sensing_data = self.show_sensing_data(plant_id)
        # Convert the dictionary into a string format
        sensing_data_str = "\n".join([f"{sensor_kind}: {value[0][0]}" for sensor_kind, value in sensing_data.items()])
        self.bot.sendMessage(user_id, sensing_data_str)
        
        status_data = self.show_actuators_status(plant_id)
        # Convert the dictionary into a string format
        status_data_str = "\n".join([f"{device_name}: {status}" for device_name, status in status_data.items()])
        self.bot.sendMessage(user_id, status_data_str)

    
    def send_pdf(self, chat_id, file_path):
        try:
            with open(file_path, 'rb') as file:
                self.bot.sendDocument(chat_id, document=file)
        except Exception as e:
            self.bot.sendMessage(chat_id, f"Failed to send PDF file: {e}")
        


if __name__ == "__main__":
    bot = TeleBot(Config)
    
    flag = True
    i = 0
    try:
        while flag:
            time.sleep(5)
            if not i % Config.SERVICE_REGISTERATION_INTERVAL:
                bot.bot_manager.post_service()
            i+= 5
    except KeyboardInterrupt:
        flag = False