#!/bin/bash

__USER=$USER

# Get super user privileges
if [[ $EUID != 0 ]]; then
	sudo -E "$0" "$@"
	exit $?
fi

REGISTRY=10.51.0.39:5000
NTP_IP=10.50.0.3

logfile=/install.log
exec > $logfile 2>&1

apt update 
apt install -y docker.io chrony

linenum=`grep iburst -nr /etc/chrony/chrony.conf | cut -d : -f 1`
sed -i "${linenum}s/.*/pool ${NTP_IP} iburst/" /etc/chrony/chrony.conf
service chrony restart

echo '============= Pulling images ==============='

echo '{ "insecure-registries" : ["'$REGISTRY'"] }' > /etc/docker/daemon.json
service docker restart

docker pull python:2-alpine
docker pull $REGISTRY/is-rabbitmq:3
docker pull $REGISTRY/camera-gateway:1.1
docker pull $REGISTRY/mjpeg-server:1
docker pull $REGISTRY/aruco:1
docker pull $REGISTRY/sync:1
docker pull $REGISTRY/robot-controller:1

echo '============= Installation finished ==============='

docker run -d --network=host -p8000:8000 python:2-alpine python -m SimpleHTTPServer