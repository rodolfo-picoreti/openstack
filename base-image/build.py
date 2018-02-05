import shade
import json
import sys
import requests
from time import sleep

base_image_name = 'docker-base'
base_image = 'urn:publicid:IDN+futebol.inf.ufes.br+image+img-ubuntu16-cloud'
network_name = 'provider'
flavor_name = 'm1.small' 
script_path = './install.sh'
key_pair_name = 'ninja'
probe_interval_s = 5

shade.simple_logging(debug=True)
cloud = shade.openstack_cloud(cloud='prod')

if cloud.get_image(base_image_name) is None:
  cloud.delete_server(base_image_name)
  server = cloud.create_server(
    name = base_image_name,
    image = base_image,
    flavor = cloud.get_flavor(flavor_name),
    network = network_name,
    userdata = open(script_path, 'r').read(),
    key_name = key_pair_name,
  )
  cloud.wait_for_server(server)
  server = cloud.get_server(base_image_name)
  print json.dumps(server, indent=4)
  ip = server.public_v4

  while True:
    try:
      print '[INFO] Checking if build finished'
      r = requests.get('http://{}:8000'.format(ip))
      print '[INFO] Build done, saving snapshot...'
      cloud.create_image_snapshot(base_image_name, base_image_name, wait=True)
      cloud.delete_server(base_image_name)
      print '[INFO] All done' 
      sys.exit(0)
    except:
      print '[INFO] Not yet, waiting {}s'.format(probe_interval_s)
      sleep(probe_interval_s)

else:
  print '[INFO] Image already exists...'
