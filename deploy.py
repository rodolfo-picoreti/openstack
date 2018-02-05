import pystache
import os
import shade
import json

docker_registry = '10.51.0.39:5000'
zipkin_host = '10.51.0.39'
zipkin_port = 9411
camera_ips = ['10.51.100.2', '10.51.100.3', '10.51.101.2', '10.51.101.3']
base_image = 'docker-base'
key_value_name = 'ninja'


def docker_run(image, args=[], workdir='', volume='', env=[], before=''):
    template = open('./docker_run.sh.mustache', 'r').read()
    return pystache.render(template, {
        'image': '{}/{}'.format(docker_registry, image),
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
            image=base_image,
            flavor=cloud.get_flavor('m1.small'),
            key_name=key_value_name,
            userdata=userdata,
        )
    else:
        print '[INFO] Server {} already running'.format(name)

    if wait == True:
        cloud.wait_for_server(server)
        server = cloud.get_server(name)
    return server


shade.simple_logging(debug=False)
cloud = shade.openstack_cloud(cloud='prod')

# RabbitMQ
server = create_server(
    cloud,
    name='RabbitMQ',
    userdata=docker_run(image='is-rabbitmq:3'),
    wait = True,
)
broker_uri = 'amqp://{}'.format(server.public_v4)

# Camera Gateways
for n, camera in enumerate(camera_ips):
    create_server(
        cloud,
        name='CameraGateway.{}'.format(n),
        userdata=docker_run(
            image='camera-gateway:1.1',
            args=["./service", "-i", n, "-c", camera, "-u", broker_uri,
                  "-s", "1400", "-d", "6000", "-z", zipkin_host, "-p", zipkin_port],
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
                  "-z", zipkin_host, "-p", zipkin_port],
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
              "-z", zipkin_host, "-P", zipkin_port],
    )
)
