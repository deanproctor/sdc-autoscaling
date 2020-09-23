# Lambda Setup:
  1. Create a new Lambda function
	  1. Runtime: Python 3.7
	  2. Copy/paste the included lambda_function.py
	  3. Update the lambda function to include your Control Hub details
  2. Add a trigger to the function, select API Gateway
	  1. Choose "Create an API"
	  2. Type: "REST API"
	  3. Security: API key

# Script Installation:
  1. Save the autoscale script to: /opt/streamsets-datacollector/bin/
  2. Save autoscale.conf to: /etc/sdc/
  3. Save sdc.service to: /etc/systemd/system/
  4. Run: chmod 755 /opt/streamsets-datacollector/bin/autoscale
  5. Run: sudo systemctl daemon-reload

# Configuration:
  1. Edit /etc/sdc/autoscale.conf to set your config
	  * Include the API Endpoint and API Key from the Lambda setup
