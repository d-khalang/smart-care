# Import Flask and other necessary modules
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
import requests
from data_manager import DataManager
from config import MyLogger, Config

# Your Flask app definition and other code...
app = Flask(__name__)
app.secret_key = Config.FLASK_SECURITY_KEY
        

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
    logger.info(device_info)
    # Call the send_status_message function with device_id and status here
    try:

        data_manager.post_device_status(device_info)

    except requests.exceptions.RequestException as e:
        logger.error(f"failed to send the device status. Error:{e}")

    finally:
        data_manager.stop_mqtt()

    if status == "DISABLE":
        return jsonify({'message': f'{status} status not available at the moment'})
    return jsonify({'message': 'Status message sent successfully'})
    

# Route to handle the "Get Report" button click
@app.route('/get_report/<int:plant_id>', methods=['GET'])
def get_report(plant_id):
    if not session.get('logged_in') or session.get('plant_id') != plant_id:
        return redirect(url_for('login', plant_id=plant_id))

    try:
        report_path = data_manager.get_report(plant_id)
        return send_file(report_path, as_attachment=True, download_name=f'plant_{plant_id}_report.pdf')
    except Exception as e:
        logger.error(f"Failed to get report for plant {plant_id}. Error: {e}")
        return jsonify({'error': 'Failed to get report'}), 500


# Route to display the index page
@app.route('/')
def index():

    data_manager.update_plant_list()
    plants = data_manager.get_plants()
    return render_template('index.html', plants=plants)


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        plant_id = request.form['plant_id']
        
        if data_manager.authenticate_user(plant_id, username, password):
            plant_id = int(plant_id)
            logger.debug(f"plant_id: {plant_id}, user_name: {username}, password: {password,type(password)}")
            session['logged_in'] = True
            session['plant_id'] = plant_id
            logger.info(f"Redirecting to plant detail for page {plant_id}")
            return redirect(url_for('plant_detail', plant_id=plant_id))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login', plant_id=plant_id))
    
    plant_id = request.args.get('plant_id')
    return render_template('login.html', plant_id=plant_id)


# Dynamic route for each plant
@app.route('/plant/<int:plant_id>')
def plant_detail(plant_id):
    if not session.get('logged_in') or session.get('plant_id') != plant_id:
        return redirect(url_for('login', plant_id=plant_id))

    data_manager.update_plant_list()
    plants = data_manager.get_plants()
    room_id = data_manager.get_room_for_plant(int(plant_id))
    devices = data_manager.get_devices_for_plant(int(room_id), int(plant_id))
    channelDetail = data_manager.get_channel_detail(str(room_id))
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
        return render_template('plant_detail.html', 
                               plant=plant, 
                               devices=devices, 
                               channelID=channel_id, 
                               fields=filtered_fields, 
                               get_button_class=get_button_class)
    else:
        return "Plant not found."

if __name__ == '__main__':
    data_manager = DataManager()
    logger = MyLogger.get_main_loggger()
    app.run(host='0.0.0.0', port=5000, debug=True)
    # plant_detail(101)
