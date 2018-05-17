import os
import shade
import json

config = json.load(open('config.json'))
cloud_name = config['selected']
config = config[cloud_name]
print json.dumps(config, indent=4)

shade.simple_logging(debug=True)
cloud = shade.openstack_cloud(cloud=cloud_name)

cloud.delete_server('RabbitMQ')
for n, camera in enumerate(config['camera_ips']):
    cloud.delete_server('CameraGateway.{}'.format(n))

cloud.delete_server('MjpegServer')

for n in xrange(4):
    cloud.delete_server('ArUco.{}'.format(n))

cloud.delete_server('Time.Sync')
cloud.delete_server('RobotController')
