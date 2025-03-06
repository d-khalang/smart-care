import json
import requests
import re
import os
from huggingface_hub import InferenceClient
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from datetime import datetime
from typing import Literal
from config import Config, MyLogger


class DataManager():
    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.set_logger(config.DATA_MANAGER_LOGGER)
        self.catalog_address = self.config.CATALOG_URL
        self.endpoint_cache = {}
        # self.post_service()
        self.logger.info("Initiating the data manager...")


    def _get_plant(self, plant_id):
        endpoint, host = self._discover_service_plus(self.config.PLANTS_ENDPOINT, 'GET')
        output = []
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if plant_id:
                    url += f"/{plant_id}"
            else:
                self.logger.error(f"Failed to get plant endpoint")
                
            
            self.logger.info(f"Fetching sensors information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            plants_response = response.json()

            if plants_response.get("success"):
                plants_list = plants_response["content"]
                if plants_list:
                    output = plants_list
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch devices information: {e}")
            
        return output


    def _get_rooms(self, room_id: str):
        endpoint, host = self._discover_service_plus(self.config.ROOMS_ENDPOINT, 'GET')
        output = []
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}"
                if room_id:
                    url += f"/{room_id}"
            else:
                self.logger.error(f"Failed to get rooms endpoint")
                
            self.logger.info(f"Fetching rooms information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            rooms_response = response.json()

            if rooms_response.get("success"):
                rooms_list = rooms_response["content"]
                if rooms_list:
                    output = rooms_list
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch rooms information: {e}")
            
        return output

    
    def get_LLM(self):
        endpoint, host = self._discover_service_plus(self.config.GENERAL_ENDPOINT, 'GET')
        output = {}
        try:
            if endpoint:    
                url = f"{self.catalog_address}{endpoint}/llm"
            else:
                self.logger.error(f"Failed to get LLM's endpoint")
                
            self.logger.info(f"Fetching LLM information from {url}")
            response = requests.get(url)
            response.raise_for_status()
            json_data = response.json()

            if json_data.get("success"):
                data = json_data.get("content", [[]])
                output = data.get("llm",{})
                if output:
                    self.logger.info("LLM info received.")
        
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch LLM's information: {e}")
        return output


    def _get_room_for_plant(self, plant_id):
        plants = self._get_plant(plant_id=plant_id)
        for plant in plants:
            if plant["plantId"] == int(plant_id):
                return plant["roomId"]
        return 0    


    def get_sensing_data(self, plant_id: str, room_id: str = None, results: int = 4, start_date: str = None, end_date: str = None):
        endpoint, host = self._discover_service_plus(item=self.config.ADAPTOR_SENSING_DATA_ENDPOINT, 
                                                    method='GET',
                                                    microservice=self.config.THINGSPEAK_ADAPTOR_REGISTRY_NAME)
        
        if not room_id:
            room_id = self._get_room_for_plant(plant_id)
            if not room_id:
                self.logger.error(f"No room_id detected for plant {plant_id}")
                return
        
        local_vars = {
        'results': results,
        'start_date': start_date,
        'end_date': end_date,
        'plant_id': plant_id
        }
        
        params = {k: v for k, v in local_vars.items() if v is not None}
        try:
            if endpoint and host:    
                url = f"{host}{endpoint}/{room_id}"
                req_g = requests.get(url=url, params=params)
                req_g.raise_for_status()
                self.logger.info(f"Sensing data for room {room_id} with params: {params} received.")
                sensing_data_response = req_g.json()
                if not sensing_data_response.get("success"):
                    self.logger.error(f"Failed to get sensing data with response: {sensing_data_response}.")
                    return {}
                return sensing_data_response.get("content")
                
            else:
                self.logger.error(f"Failed to get sensing data endpoint")
                return {}
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetchsensing data: {e}")
            return {}


    def get_adjacent_plant_id(self, room_id: str, plant_id: str):
        if not room_id:
            plants = self._get_plant(plant_id)
            if not plants:
                return None
            plant = plants[0]
            room_id = str(plant.get("roomId", ""))
    
        # If room_id is still not found, return None
        if not room_id:
            return None
        rooms = self._get_rooms(room_id=room_id)
        if not rooms:
            return None

        plants = rooms[0].get("plantInventory", [])
        for the_plant_id in plants:
            if str(the_plant_id) != str(plant_id):
                return str(the_plant_id)
        return None


    def post_service(self):
        # Read the JSON file
        try:
            with open(self.config.SERVICE_REGISTRY_FILE, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            self.logger.error(f"Service registry file not found: {self.config.SERVICE_REGISTRY_FILE}")
            return
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from file: {self.config.SERVICE_REGISTRY_FILE}")
            return

        # Post the data to the registry system
        url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}"
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            if response.json().get("success"): 
                self.logger.info("Service registered successfully.")
            else:
                self.logger.error("Error registring the service.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error posting service data: {str(e)}")
        


    def _discover_service_plus(self, item: str, method: Literal['GET', 'POST', 'PUT', 'DELETE'], sub_path: str=None, microservice: str=Config.SERVICE_REGISTRY_NAME):
        # Return the endpoint from the cache
        if item in self.endpoint_cache and method in self.endpoint_cache[item]:
            return self.endpoint_cache[item][method], self.endpoint_cache[item]['host']

        try:
            url = f"{self.catalog_address}/{self.config.SERVICES_ENDPOINT}/{microservice}"
            response = requests.get(url)
            response.raise_for_status()

            service_response = response.json()

            if service_response.get("success"):
                # Extract the service registry from the response
                service_registry = service_response.get("content", [[]])
                service = service_registry[0]
                if service:
                    endpoints = service.get("endpoints", [])
                    host = service.get("host", "")
                    for endpoint in endpoints:
                        path = endpoint.get("path", "")
                        service_method = endpoint.get("method", "")

                        if item in path and method == service_method:
                            if sub_path:
                                if sub_path in path:
                                    self.endpoint_cache.setdefault(item, {})[method] = path
                                    self.endpoint_cache[item]["host"] = host
                                    return path, host
                            else:
                                self.endpoint_cache.setdefault(item, {})[method] = path
                                self.endpoint_cache[item]["host"] = host
                                return path, host
                            
            self.logger.error(f"Failed to discover service endpoint")

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch services endpoint: {e}")




class Reporter():
    def __init__(self, config: Config):
        self.config = config
        self.logger = MyLogger.get_main_loggger()
        self.catalog_address = self.config.CATALOG_URL
        self.data_manager = DataManager(config=config)
        self.LLM_dict = self.data_manager.get_LLM()
        self.logger.info("Initiating the reporter...")
        self.client = InferenceClient(api_key=self.LLM_dict.get("key",""))


    def generate_report(self, plant_id: str, room_id: str = None, results: int = 4, start_date: str = None, end_date: str = None):
        raw_data = self.data_manager.get_sensing_data(plant_id, room_id, results, start_date, end_date)
        if not raw_data:
            self.logger.error("No data detected.")
            return
        
        processed_data = self.preprocess_data(raw_data)
        averages = self.calculate_averages(processed_data)
        trends = self.detect_trends(processed_data)
        anomalies = self.detect_anomalies(processed_data)
        adjacent_plant_id = self.data_manager.get_adjacent_plant_id(room_id, plant_id)
        
        if adjacent_plant_id:
            room_data = self.data_manager.get_sensing_data(adjacent_plant_id, room_id, results, start_date, end_date)
            room_data_processed = self.preprocess_data(room_data)
            comparisons = self.comparative_analysis(processed_data, room_data_processed, adjacent_plant_id)
        else:
            comparisons = {}
        
        correlations = self.calculate_correlations(processed_data)
        daily_summary = self.summarize_daily(processed_data)

        report = {
            "averages": averages,
            "trends": trends,
            "anomalies": anomalies,
            "comparisons": comparisons,
            "correlations": correlations,
            "daily_summary": daily_summary
        }

        self.logger.info("Generated report: %s", report)
        return report
    
    def preprocess_data(self, data):
        # Convert to time-series format and normalize data
        processed_data = {}
        for key, values in data.items():
            timeseries = [(float(value[0]), value[1]) for value in values]
            processed_data[key] = timeseries
        return processed_data


    def calculate_averages(self, data):
        averages = {}
        for key, values in data.items():
            avg = sum(value[0] for value in values) / len(values)
            averages[key] = avg
        return averages


    def detect_trends(self, data):
        trends = {}
        for key, values in data.items():
            initial = values[0][0]
            final = values[-1][0]
            trends[key] = 'increasing' if final > initial else 'decreasing' if final < initial else 'stable'
        return trends
    
    def detect_anomalies(self, data):
        anomalies = {}
        for key, values in data.items():
            mean = sum(value[0] for value in values) / len(values)
            variance = sum((value[0] - mean) ** 2 for value in values) / len(values)
            std_dev = variance ** 0.5
            anomalies[key] = [(value, timestamp) for value, timestamp in values if abs(value - mean) > 2 * std_dev]
        return anomalies
    
    def calculate_correlations(self, data):
        correlations = {}
        keys = list(data.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                key1, key2 = keys[i], keys[j]
                values1 = [value[0] for value in data[key1]]
                values2 = [value[0] for value in data[key2]]
                if len(values1) == len(values2):
                    mean1, mean2 = sum(values1) / len(values1), sum(values2) / len(values2)
                    covariance = sum((x - mean1) * (y - mean2) for x, y in zip(values1, values2)) / len(values1)
                    std_dev1 = (sum((x - mean1) ** 2 for x in values1) / len(values1)) ** 0.5
                    std_dev2 = (sum((y - mean2) ** 2 for y in values2) / len(values2)) ** 0.5
                    correlations[(key1, key2)] = covariance / (std_dev1 * std_dev2) if std_dev1 and std_dev2 else 0
        return correlations

    def summarize_daily(self, data):
        daily_summary = {}
        for key, values in data.items():
            summary = {}
            for value, timestamp in values:
                date = timestamp.split('T')[0]
                if date not in summary:
                    summary[date] = []
                summary[date].append(value)
            daily_summary[key] = {date: sum(vals) / len(vals) for date, vals in summary.items()}
        return daily_summary


    def comparative_analysis(self, plant_data, room_data, plant_id):
        comparisons = {}
        shared_keys = ['light', 'temperature']
        
        for key in plant_data:
            if any(key.startswith(shared_key) for shared_key in shared_keys):
                # Skip keys that are shared sensors data (light and temperature)
                continue
            
            plant_specific_key = f"{key}-{plant_id}"
            plant_values = [value[0] for value in plant_data[key]]
            room_values = [value[0] for value in room_data.get(plant_specific_key, [])]
            
            if room_values:
                plant_avg = sum(plant_values) / len(plant_values)
                room_avg = sum(room_values) / len(room_values)
                comparisons[key] = plant_avg - room_avg

        # Handle shared sensor data
        for shared_key in shared_keys:
            plant_values = [value[0] for value in plant_data.get(shared_key, [])]
            room_values = [value[0] for value in room_data.get(shared_key, [])]
            
            if plant_values and room_values:
                plant_avg = sum(plant_values) / len(plant_values)
                room_avg = sum(room_values) / len(room_values)
                comparisons[shared_key] = plant_avg - room_avg

        return comparisons


    def create_pdf_report(self, report, plant_id, room_id=None):
        file_name = self.get_unique_file_name(f"Plant_Report_{plant_id}.pdf")
        doc = SimpleDocTemplate(file_name, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        elements = []

        # Title Page
        title = Paragraph("Plant Monitoring Report", styles['Title'])
        elements.append(title)
        subtitle = Paragraph(f"Plant ID: {plant_id}", styles['Title'])
        elements.append(subtitle)
        if room_id:
            subtitle_room = Paragraph(f"Room ID: {room_id}", styles['Title'])
            elements.append(subtitle_room)
        date = Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Title'])
        elements.append(date)
        elements.append(Spacer(1, 0.5 * inch))

        # Summary Section
        summary_title = Paragraph("Summary", styles['Heading2'])
        elements.append(summary_title)
        summary_text = f"This report provides a detailed analysis of the plant monitoring data for plant ID {plant_id}"
        if room_id:
            summary_text += f" in room ID {room_id}"
        summary_text += f". The data covers the period from {report.get('start_date', 'N/A')} to {report.get('end_date', 'N/A')}."
        summary_paragraph = Paragraph(summary_text, styles['BodyText'])
        elements.append(summary_paragraph)
        elements.append(Spacer(1, 0.2 * inch))

        # Averages Section
        averages_title = Paragraph("Averages", styles['Heading2'])
        elements.append(averages_title)
        averages_data = [['Parameter', 'Average Value', 'Unit']]
        units = {'temperature': '°C', 'light': 'μmol/m²/s', 'ph': 'pH', 'soil_moisture': '%'}
        
        for key, avg in report['averages'].items():
            # Clean the key to remove '-{plant_id}' if it exists
            cleaned_key = key.split('-')[0]  # This removes any suffix like '-101'
            units_key = units.get(cleaned_key, '')
            averages_data.append([cleaned_key.capitalize(), f"{avg:.2f}", units_key])
        
        averages_table = Table(averages_data)
        averages_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(averages_table)
        elements.append(Spacer(1, 0.2 * inch))

        # Trends Section
        trends_title = Paragraph("Trends", styles['Heading2'])
        elements.append(trends_title)
        trends_paragraph = Paragraph("The following trends have been observed in the data:", styles['BodyText'])
        elements.append(trends_paragraph)
        for key, trend in report['trends'].items():
            cleaned_key = key.split('-')[0]  # Clean the key
            trend_text = f"- {cleaned_key.capitalize()}: {trend}"
            elements.append(Paragraph(trend_text, styles['BodyText']))
        elements.append(Spacer(1, 0.2 * inch))

        # Anomalies Section
        anomalies_title = Paragraph("Anomalies", styles['Heading2'])
        elements.append(anomalies_title)
        anomalies_paragraph = Paragraph("Detected anomalies are listed below with their corresponding timestamps:", styles['BodyText'])
        elements.append(anomalies_paragraph)
        for key, anomalies in report['anomalies'].items():
            cleaned_key = key.split('-')[0]  # Clean the key
            anomaly_text = f"<b>{cleaned_key.capitalize()}:</b> {len(anomalies)} anomalies detected"
            elements.append(Paragraph(anomaly_text, styles['BodyText']))
            for anomaly in anomalies:
                anomaly_detail = f"Value: {anomaly[0]}, Timestamp: {anomaly[1]}"
                elements.append(Paragraph(anomaly_detail, styles['BodyText']))
        elements.append(Spacer(1, 0.2 * inch))

        # Comparisons Section
        comparisons_title = Paragraph("Comparisons", styles['Heading2'])
        elements.append(comparisons_title)
        comparisons_paragraph = Paragraph("Comparison of plant data with other plants in the room data (if applicable):", styles['BodyText'])
        elements.append(comparisons_paragraph)
        for key, comparison in report['comparisons'].items():
            cleaned_key = key.split('-')[0]  # Clean the key
            comparison_text = f"- {cleaned_key.capitalize()}: Difference = {comparison:.2f} {units.get(cleaned_key, '')}"
            elements.append(Paragraph(comparison_text, styles['BodyText']))
        elements.append(Spacer(1, 0.2 * inch))

        # Correlations Section
        correlations_title = Paragraph("Correlations", styles['Heading2'])
        elements.append(correlations_title)
        correlations_paragraph = Paragraph("The following correlations between different parameters were found:", styles['BodyText'])
        elements.append(correlations_paragraph)
        for key_pair, correlation in report['correlations'].items():
            cleaned_key1 = key_pair[0].split('-')[0]  # Clean the key
            cleaned_key2 = key_pair[1].split('-')[0]  # Clean the key
            correlation_text = f"- {cleaned_key1.capitalize()} and {cleaned_key2.capitalize()}: Correlation = {correlation:.2f}"
            elements.append(Paragraph(correlation_text, styles['BodyText']))
        elements.append(Spacer(1, 0.2 * inch))

        # Daily Summary Section
        daily_summary_title = Paragraph("Daily Summary", styles['Heading2'])
        elements.append(daily_summary_title)
        daily_summary_data = [['Date', 'Parameter', 'Average Value', 'Unit']]
        for key, daily_data in report['daily_summary'].items():
            cleaned_key = key.split('-')[0]  # Clean the key
            for date, avg in daily_data.items():
                daily_summary_data.append([date, cleaned_key.capitalize(), f"{avg:.2f}", units.get(cleaned_key, '')])
        daily_summary_table = Table(daily_summary_data)
        daily_summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(daily_summary_table)
        elements.append(Spacer(1, 0.2 * inch))

        # LLM Insights Section
        llm_message = self.generate_llm_insight(report)  # Get insights from the LLM
        if llm_message:
            llm_insights_title = Paragraph("Insights", styles['Heading2'])
            elements.append(llm_insights_title)
            
            # Adjust the message: remove stars and format the text in bold
            # This regex finds text wrapped in ** and replaces it with <b> for bolding
            formatted_message = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', llm_message)
            
            # Ensure a newline after the bolded section
            formatted_message = formatted_message.replace('<b>', '\n<b>').replace('</b>', '</b>\n')
            
            # Split the message into paragraphs where a line starts with '-'
            insight_paragraphs = formatted_message.split('\n')
            
            # Add each paragraph to the PDF
            for paragraph in insight_paragraphs:
                paragraph = paragraph.strip()  # Remove extra spaces
                
                # Skip empty paragraphs
                if paragraph:
                    insights_paragraph = Paragraph(paragraph, styles['BodyText'])
                    elements.append(insights_paragraph)
                    elements.append(Spacer(1, 0.1 * inch))  # Add some space between paragraphs
            
            # Add spacing before the next section
            elements.append(Spacer(1, 0.3 * inch))

        # Build the PDF
        doc.build(elements)
        self.logger.info("PDF report created: %s", file_name)
        return file_name


    def generate_llm_insight(self, report):
        # Prepare the message for the LLM to analyze the report data
        plant_id = report.get('plant_id', 'unknown')
        message = f"""
            Here is the collected data for plant {plant_id} which is lettuce:

            Temperature: {report.get('averages', {}).get('temperature', 'N/A')} °C
            Light: {report.get('averages', {}).get('light', 'N/A')} μmol/m²/s
            pH: {report.get('averages', {}).get(f'ph-{plant_id}', 'N/A')}
            Soil Moisture: {report.get('averages', {}).get(f'soil_moisture-{plant_id}', 'N/A')} %

            Trends observed: 
            {', '.join([f"{key}: {value}" for key, value in report.get('trends', {}).items()])}

            Anomalies:
            {', '.join([f"{key}: {len(value)} anomalies" for key, value in report.get('anomalies', {}).items()])}


            Please provide insights based on this data. Focus on identifying any trends, anomalies, correlations, or areas for improvement. Format the output as follows:
            1. **Key Findings:** Summarize the most important findings.
            2. **Actionable Insights:** Provide suggestions for corrective actions or improvements.
            3. **Potential Issues:** Identify any potential problems or risks based on the data.

            Please be concise, clear, and break your response into sections with appropriate headers.

            """


        # Set up the LLM message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": message
                    },
                    {
                        "type": "text",
                        "text": "Please don't rewrite the data. Just provide actionable insights."
                    }
                ]
            }
        ]

        # Request insights from the LLM
        stream = self.client.chat.completions.create(
            model=self.LLM_dict.get("model",""), 
            messages=messages, 
            max_tokens=500,
            stream=True
        )

        # Collect the LLM's response
        insight = ""
        for chunk in stream:
            insight += chunk.choices[0].delta.content

        return insight.strip()
    
    def get_unique_file_name(self, base_file_name):
        base_name, extension = os.path.splitext(base_file_name)
        counter = 1
        file_name = base_file_name
        while os.path.exists(file_name):
            file_name = f"{base_name}_v{counter}{extension}"
            counter += 1
        return file_name
    
    def generate_and_deliver_report(self, plant_id: str, room_id: str = None, results: int = 50, start_date: str = None, end_date: str = None):
        report = self.generate_report(plant_id, room_id, results, start_date, end_date)
        pdf_report_name = self.create_pdf_report(report, plant_id, room_id)
        return pdf_report_name


# if __name__ == "__main__":
#     reporter = Reporter(Config)
#     data = reporter.data_manager.get_sensing_data(plant_id='101', results=30, start_date="2024-12-10")
#     print(data)
#     # pre_data = reporter.preprocess_data(data)
#     # print(pre_data)
#     # print()
#     # print(reporter.calculate_averages(pre_data))
#     # print()
#     # print(reporter.detect_trends(pre_data))
#     # print()
#     # print(reporter.detect_anomalies(pre_data))
#     # print()
#     # print(reporter.calculate_correlations(pre_data))
#     # print()
#     # print(reporter.summarize_daily(pre_data))
#     report = reporter.generate_report(plant_id='101', results=100, start_date="10-12-2024")
#     reporter.create_pdf_report(report, "101")

