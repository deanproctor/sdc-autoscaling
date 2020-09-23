#!/usr/bin/env bash
set -e

######################
# Config
######################

SDC_VERSION=3.18.1
SDC_ROOT=/opt
SDC_HOME=$SDC_ROOT/streamsets-datacollector
SDC_CONF=/etc/sdc
SDC_LOG=/var/log/sdc
SDC_DATA=/var/lib/sdc
SDC_RESOURCES=/var/lib/sdc-resources
SDC_USER=sdc
SDC_GROUP=sdc
SDC_PORT=18630
SDC_TIMEZONE=UTC
OS_PACKAGES="core aws-lib aws-secrets-manager-credentialstore-lib crypto-lib jdbc-lib jms-lib jython_2_7-lib mapr_6_1-lib mapr_6_1-mep6-lib orchestrator-lib wholefile-transformer-lib"
ENT_PACKAGES="snowflake-lib-1.4.0"
# bash or lambda
AUTOSCALE=lambda


######################
# Installation Script
######################

echo "Creating installation directories"
sudo mkdir -p $SDC_ROOT $SDC_CONF $SDC_LOG $SDC_DATA $SDC_RESOURCES

echo "Installing dependencies"
sudo yum update -y > /dev/null
sudo yum install -y java-1.8.0 ntp wget > /dev/null

echo "Downloading StreamSets packages..."
for pkg in $OS_PACKAGES
do
  echo -e "\t$pkg"
  wget -qO - https://s3-us-west-2.amazonaws.com/archives.streamsets.com/datacollector/$SDC_VERSION/tarball/streamsets-datacollector-$pkg-$SDC_VERSION.tgz | sudo tar xzf - -C $SDC_ROOT
done

for pkg in $ENT_PACKAGES
do
  echo -e "\t$pkg"
  wget -qO - https://s3-us-west-2.amazonaws.com/archives.streamsets.com/datacollector/enterprise/tarball/enterprise/streamsets-datacollector-$pkg.tgz | sudo tar xzf - -C $SDC_HOME-$SDC_VERSION
done

echo "Renaming download directory to $SDC_HOME"
sudo mv $SDC_HOME-$SDC_VERSION $SDC_HOME

echo "Installing config files to $SDC_CONF"
sudo cp -R $SDC_HOME/etc/* $SDC_CONF

echo "Installing autoscale files"
sudo cp autoscale/$AUTOSCALE/autoscale $SDC_HOME/bin/
sudo chmod 755 $SDC_HOME/bin/autoscale

sudo cp autoscale/$AUTOSCALE/autoscale.conf $SDC_CONF/
sudo cp autoscale/sdc.service $SDC_HOME/systemd/

if [ -d "autoscale/$AUTOSCALE/private" ]; then
  sudo cp -r autoscale/$AUTOSCALE/private $SDC_CONF
  sudo chmod 600 $SDC_CONF/private/*
  sudo chmod 750 $SDC_CONF/private
fi

echo "Creating sdc user"
sudo groupadd -r $SDC_USER && sudo useradd -r -d $SDC_HOME -g $SDC_GROUP -s /sbin/nologin $SDC_USER

echo "Setting sdc user permissions"
sudo chown -R $SDC_USER:$SDC_GROUP $SDC_HOME $SDC_CONF $SDC_LOG $SDC_DATA $SDC_RESOURCES

echo "Updating SDC configuration settings..."
echo -e "\tUpdating service directories"
sudo sed -i "s@/opt/streamsets-datacollector@$SDC_HOME@" $SDC_HOME/systemd/sdc.service
sudo sed -i "s@/etc/sdc@$SDC_CONF@" $SDC_HOME/systemd/sdc.service
sudo sed -i "s@/var/log\/sdc@$SDC_LOG@" $SDC_HOME/systemd/sdc.service
sudo sed -i "s@/var/lib/sdc@$SDC_DATA@" $SDC_HOME/systemd/sdc.service

echo -e "\tEnabling HTTPS"
sudo sed -i 's/http.port=18630/http.port=-1/' $SDC_CONF/sdc.properties
sudo sed -i "s/https.port=-1/https.port=$SDC_PORT/" $SDC_CONF/sdc.properties

echo -e "\tIncreasing batch and parser limits"
sudo sed -i 's/production.maxBatchSize=.*/production.maxBatchSize=100000/' $SDC_CONF/sdc.properties
sudo sed -i 's/#parser.limit=.*/parser.limit=5335040/' $SDC_CONF/sdc.properties

TOTAL_MEM=$(free -m | grep Mem | awk '{print $2}')
JAVA_MEM=$(awk "BEGIN {printf \"%.0f\",$TOTAL_MEM*.8}")
echo -e "\tIncreasing JVM memory to ${JAVA_MEM}M"
sudo sed -i "s/-Xmx1024m -Xms1024m/-Xmx${JAVA_MEM}m -Xms${JAVA_MEM}m/" $SDC_HOME/libexec/sdc-env.sh

if [ $TOTAL_MEM -gt 8192 ]; then
  echo -e "\tChanging garbage collector to G1GC"
  sudo sed -i 's/-XX:+UseConcMarkSweepGC -XX:+UseParNewGC/-XX:+UseG1GC/' $SDC_HOME/libexec/sdc-env.sh
fi

echo -e "\tInstalling SDC CLI options"
echo "export SDC_CLI_JAVA_OPTS=\"-Djavax.net.ssl.trustStore=$SDC_CONF/keystore.jks -Djavax.net.ssl.trustStorePassword=password\"" >> ~/.bash_profile
echo "PATH=\$PATH:$SDC_HOME/bin" >> ~/.bash_profile
source ~/.bash_profile

echo "Setting system timezone to $SDC_TIMEZONE"
sudo timedatectl set-timezone $SDC_TIMEZONE

echo "Installing sdc service files"
sudo cp $SDC_HOME/systemd/sdc.service /etc/systemd/system/sdc.service
sudo cp $SDC_HOME/systemd/sdc.socket /etc/systemd/system/sdc.socket
sudo systemctl daemon-reload

echo "Starting ntp service"
sudo systemctl -q enable ntpd
sudo systemctl -q start ntpd

echo "Enabling sdc service"
sudo systemctl -q enable sdc

echo "Installation Complete"
