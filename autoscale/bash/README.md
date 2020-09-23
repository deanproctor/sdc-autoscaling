# Installation:
  1. Save the autoscale script to: /opt/streamsets-datacollector/bin/
  2. Save autoscale.conf to: /etc/sdc/
  3. Save sdc.service to: /etc/systemd/system/
  4. Run: chmod 755 /opt/streamsets-datacollector/bin/autoscale
  5. Run: sudo systemctl daemon-reload

# Configuration:
  1. Edit /etc/sdc/autoscale.conf to set your config
  2. If storing authentication credentials on disk:
     1. chown the credential files to the sdc user
     2. chmod the credential files 600
