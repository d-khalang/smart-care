# Import Flask and other necessary modules
from flask import Flask, render_template, request, jsonify
import requests
from data_manager import DataManager

# Your Flask app definition and other code...
app = Flask(__name__)






        

def get_button_class(status):
    if status == ('ON'or'OPEN'):
        return 'green'
    elif status == ('OFF' or 'CLOSE'):
        return 'blue'
    elif status == 'DISABLE':
        return 'red'
    else:
        return 'orange'  # Default color 

    
# Flask route to handle button clicks
@app.route('/send_status_message', methods=['POST'])
def send_status_message():
    device_info = request.json
    status = device_info["status"]
    print(device_info)
    # Call the send_status_message function with device_id and status here
    try:

        user_awareness.post_device_status(device_info)

    except requests.exceptions.RequestException as e:
        print(f"failed to send the device status. Error:{e}")

    finally:
        user_awareness.stop_mqtt()

    if status == "DISABLE":
        return jsonify({'message': f'{status} status not available at the moment'})
    return jsonify({'message': 'Status message sent successfully'})
    


# Route to display the index page
@app.route('/')
def index():

    user_awareness.update_plant_list()
    plants = user_awareness.get_plants()
    return render_template('index.html', plants=plants)

# Dynamic route for each plant
@app.route('/plant/<int:plant_id>')
def plant_detail(plant_id):
    
    user_awareness.update_plant_list()
    plants = user_awareness.get_plants()
    room_id = user_awareness.get_room_for_plant(int(plant_id))
    devices = user_awareness.get_devices_for_plant(int(room_id), int(plant_id))
    channelDetail = user_awareness.get_channel_detail(str(room_id))
    channel_id = channelDetail.get("channelId") if channelDetail else 2660510
    # swapping the field number and data type
    the_fields = {v: k for k, v in channelDetail.get("fields", {}).items()} if channelDetail else {}
    filtered_fields = {
        k.rstrip(f"-{plant_id}") if k.endswith(f"-{plant_id}") else k: v 
        for k, v in the_fields.items() 
        if k in ["light", "temperature"] or k.endswith(f"-{plant_id}")
    }
    
    
    # Find the plant with the specified plant_id
    plant = next((p for p in plants if p.get('plantId') == plant_id), None)
    
    if plant:
        return render_template('plant_detail.html', plant=plant, devices=devices, channelID=channel_id, fields=filtered_fields, get_button_class=get_button_class)
    else:
        return "Plant not found."

if __name__ == '__main__':
    user_awareness = DataManager()
    app.run(debug=True)
    plant_detail(101)
