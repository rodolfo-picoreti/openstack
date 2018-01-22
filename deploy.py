from base64 import b64encode
from openstack import connection
import pystache
import os


def load_environ_credentials():
    return {
        'auth_url': os.environ['OS_AUTH_URL'],
        'project_name': os.environ['OS_PROJECT_NAME'],
        'username': os.environ['OS_USERNAME'],
        'password': os.environ['OS_PASSWORD'],
        'project_id': os.environ['OS_PROJECT_ID'],
        'project_domain_name': 'default',
        'user_domain_name': os.environ['OS_USER_DOMAIN_NAME'],
        'version': '2'
    }


def deploy(conn, image, name, args=[], env=[], key_pair='ninja', flavor='m1.tiny',
           network='Net22', vm='docker-base-ntp', ip='', workdir='', before='', volume=''):
    template = "#!/bin/bash\n"
    template += "{{before}}\n"
    template += "sudo docker pull {{image}}\n"
    template += "sudo docker run -d --restart=always --network=host "
    template += "{{#name}}--name {{.}}{{/name}} {{#workdir}}-w {{.}}{{/workdir}} "
    template += "{{#volume}}-v {{.}}{{/volume}} {{#env}}-e {{.}} {{/env}} "
    template += "{{image}} {{#args}}{{.}} {{/args}}"

    init_script = pystache.render(template, {
        'name': name,
        'image': image,
        'args': args,
        'workdir': workdir,
        'before': before,
        'volume': volume,
        'env': env,
    })

    print init_script

    try:
        network = {'uuid': conn.network.find_network(network).id}
        if ip != '':
            network['fixed_ip'] = ip

        return conn.compute.create_server(
            name=name,
            flavor_id=conn.compute.find_flavor(flavor).id,
            image_id=conn.compute.find_image(vm).id,
            networks=[network],
            key_name=key_pair,
            user_data=b64encode(init_script)
        )
    except:
        ignore = raw_input("Failed to create server... Continue anyway? (y/n)")
        if ignore == 'y':
            return None
        exit(-1)


def create_floating_ip(conn):
    provider_id = conn.network.find_network('provider').id
    return conn.network.create_ip(floating_network_id=provider_id)


def attach_floating_ip(conn, vm, ip):
    conn.compute.wait_for_server(vm)
    conn.compute.add_floating_ip_to_server(vm, address=ip.name)


conn = connection.Connection(**load_environ_credentials())

docker_registry = '10.61.100.253:5000'

zipkin_ip = '10.61.100.253'
zipkin_port = 9411

broker_ip = '10.0.2.200'
broker_uri = 'amqp://{}'.format(broker_ip)

#### RabbitMQ
vm = deploy(
    conn,
    image='{}/rabbitmq:3'.format(docker_registry),
    name='RabbitMQ',
    ip=broker_ip,
)

ip = create_floating_ip(conn)
attach_floating_ip(conn, vm, ip)
broker_float_ip = ip.floating_ip_address
broker_float_uri = 'amqp://{}'.format(broker_float_ip)
print 'Broker ip: http://{}:15672'.format(broker_float_ip)

#### Camera Gateways
camera_ips = ['10.61.100.2', '10.61.100.3', '10.61.101.2', '10.61.101.3']
for n in xrange(4):
    vm = deploy(
        conn,
        image='{}/camera-gateway:1.1'.format(docker_registry),
        name='CameraGateway.{}'.format(n),
        args=["./service", "-i", n, "-c", camera_ips[n],
              "-u", broker_float_uri, "-s", "1400", "-d", "6000",
              "-z", zipkin_ip, "-p", zipkin_port],
        network='provider',
    )

#### Mjpeg Server
vm = deploy(
    conn,
    image='{}/mjpeg-server:1'.format(docker_registry),
    name='MjpegServer',
    env=['IS_URI={}'.format(broker_uri)],
)

#### Aruco Detector
for n in xrange(4):
    vm = deploy(
        conn,
        before="git clone https://github.com/labviros/is-aruco-calib",
        volume="`pwd`/is-aruco-calib:/opt",
        image='{}/aruco:1'.format(docker_registry),
        name='ArUco.{}'.format(n),
        args=["./service", "-u", broker_uri, "-l", 0.3, "-d", 0, "-c", "/opt",
              "-z", zipkin_ip, "-p", zipkin_port],
    )

#### Sync Service
vm = deploy(
    conn,
    image='10.61.100.253:5000/time-sync:1',
    name='Time.Sync',
    args=["./service", "-u", broker_uri],
)

#### Robot Controller
vm = deploy(
    conn,
    image='10.61.100.253:5000/robot-controller:1',
    name='RobotController',
    args=["./service", "-u", broker_uri, "-z", zipkin_ip, "-P", zipkin_port],
)
