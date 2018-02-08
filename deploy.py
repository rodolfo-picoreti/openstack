import pystache
import os
import shade
import json

cloud_name = 'dev'
config = json.load(open('config.json'))[cloud_name]
print json.dumps(config, indent=4)


def docker_run(image, args=[], workdir='', volume='', env=[], before=''):
    template = open('./docker_run.sh.mustache', 'r').read()
    return pystache.render(template, {
        'image': '{}/{}'.format(config['docker_registry'], image),
        'args': args,
        'workdir': workdir,
        'before': before,
        'volume': volume,
        'env': env,
    })


def create_server(cloud, name, userdata, wait=False):
    server = cloud.get_server(name)
    if server is None:
        print '[INFO] Creating server {}'.format(name)
        server = cloud.create_server(
            name=name,
            image=config['base_image'],
            flavor=cloud.get_flavor('m1.small'),
            key_name=config['key_value_name'],
            userdata=userdata,
        )
    else:
        print '[INFO] Server {} already running @{}'.format(name, server.public_v4)

    if wait == True:
        cloud.wait_for_server(server)
        server = cloud.get_server(name)
    return server


shade.simple_logging(debug=True)
cloud = shade.openstack_cloud(cloud=cloud_name)

# RabbitMQ
server = create_server(
    cloud,
    name='RabbitMQ',
    userdata=docker_run(image='is-rabbitmq:3'),
    wait=True,
)
broker_uri = 'amqp://{}'.format(server.public_v4)

# Camera Gateways
for n, camera in enumerate(config['camera_ips']):
    create_server(
        cloud,
        name='CameraGateway.{}'.format(n),
        userdata=docker_run(
            image='camera-gateway:1.1',
            args=["./service", "-i", n, "-c", camera, "-u", broker_uri,
                  "-s", "1400", "-d", "6000", "-z", config['zipkin_host'], "-p", config['zipkin_port']]
        ),
    )

# Http Mjpeg Server
create_server(
    cloud,
    name='MjpegServer',
    userdata=docker_run(
        image='mjpeg-server:1',
        env=['IS_URI={}'.format(broker_uri)],
    )
)

# Aruco Detector
for n in xrange(4):
    create_server(
        cloud,
        name='ArUco.{}'.format(n),
        userdata=docker_run(
            before="git clone https://github.com/labviros/is-aruco-calib",
            volume="`pwd`/is-aruco-calib:/opt",
            image='aruco:1',
            args=["./service", "-u", broker_uri, "-l", 0.3, "-d", 0, "-c", "/opt",
                  "-z", config['zipkin_host'], "-p", config['zipkin_port']]
        )
    )

# Sync Service
create_server(
    cloud,
    name='Time.Sync',
    userdata=docker_run(
        image='sync:1',
        args=["./service", "-u", broker_uri],
    )
)

# Robot Controller
create_server(
    cloud,
    name='RobotController',
    userdata=docker_run(
        image='robot-controller:1',
        args=["./service", "-u", broker_uri,
              "-z", config['zipkin_host'], "-P", config['zipkin_port']]
    )
)
