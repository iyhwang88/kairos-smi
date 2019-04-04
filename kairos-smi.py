import os
import subprocess
import sys
import queue
import json
import threading
import argparse
# from pprint import pprint

# querys
QUERY_GPU = "nvidia-smi --query-gpu=timestamp,gpu_uuid,count,name,pstate,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader"
QUERY_APP = "nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader"


def ssh_remote_command(entrypoint, command):
    host, port = entrypoint.split(':')

    ssh = subprocess.Popen(["ssh", "-p", port, host, command],
                       shell=False,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:
        error = ssh.stderr.readlines()
        #print (sys.stderr, "ERROR: %s" % error)
    else:
        for i, res in enumerate(result):
            result[i] = res.decode('utf-8').strip().split(', ')

    return {entrypoint: result == None and [] or result}


def add_authkey(host, key_path):
    with open(key_path, 'r') as f:
        key = f.read()
    
    command = "echo {key} >> ~/.ssh/authorized_keys"

    auth = ssh_remote_command(host, command)
    return auth


def excute_smi(host):

    gpus = ssh_remote_command(host, QUERY_GPU)
    apps = ssh_remote_command(host, QUERY_APP)
        
    return gpus, apps

def get_gpus_status(hosts):

    que = []
    threads = []
    result = {}

    for _ in range(2):
        que.append(queue.Queue(maxsize=30))

    for host in hosts:
        # host_status = {"host":host}

        for i, query in enumerate([QUERY_GPU, QUERY_APP]):
            t = threading.Thread(target=lambda q, arg1, arg2: q.put(ssh_remote_command(arg1, arg2)), args=(que[i], host, query))
            threads.append(t)
    
    for t in threads:
        t.start()

    for t in threads:
        # t.join(timeout=1)
        t.join(2)    

    for i, q in enumerate(que):
        if i == 0:
            name = 'gpus'
        elif i == 1:
            name = 'apps'

        items = {}
        while not q.empty():
            items.update(q.get())
        result.update({name: items})    

    return result


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--loop', action='store_true', help='loop forever')
    parser.add_argument('-c', '--config', default='config.json', help='set config file location')
    args = parser.parse_args()

    config = args.config

    with open(config, 'r') as f:
        conf = json.load(f)

    HOSTS = conf['hosts']

    while(True):
        result = get_gpus_status(HOSTS)
        if args.loop:
            os.system('clear')
        # pprint(result['gpus'])

        for host in HOSTS:
            print('[{}] \t Running GPUs [ {} / {} ]'.format(host ,len(result['apps'][host]), len(result['gpus'][host])))
            for i, gpu in enumerate(result['gpus'][host]):
                print("| {} | Temp {:2s}C | Util {:5s} | Mem {:9s}/{:9s} |".format(i, gpu[5], gpu[6], gpu[7], gpu[8]))
            print()
        
        if not args.loop:
            break


