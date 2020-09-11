__copyright__ = "Copyright (c) 2020 Jina AI Limited. All rights reserved."
__license__ = "Apache-2.0"

import os
import sys

import urllib.request
import gzip
import numpy as np
import webbrowser

from jina.flow import Flow
from jina.clients.python import ProgressBar
from jina.helper import colored
from jina.logging import default_logger
from jina.proto import jina_pb2
from jina.drivers.helper import array2pb



from pkg_resources import resource_filename
from components import *

result_html = []
num_docs = 500
index_docs = []



def print_result(resp):
    for d in resp.search.docs:
        vi = d.uri
        result_html.append(f'<tr><td><img src="{vi}"/></td><td>')
        for kk in d.matches:
            kmi = kk.uri
            result_html.append(f'<img src="{kmi}" style="opacity:{kk.score.value}"/>')
            # k['score']['explained'] = json.loads(kk.score.explained)
        result_html.append('</td></tr>\n')


def write_html(html_path):
    with open(resource_filename('jina', '/'.join(('resources', 'helloworld.html'))), 'r') as fp, \
            open(html_path, 'w') as fw:
        t = fp.read()
        t = t.replace('{% RESULT %}', '\n'.join(result_html))
        fw.write(t)

    url_html_path = 'file://' + os.path.abspath(html_path)

    try:
        webbrowser.open(url_html_path, new=2)
    except:
        pass
    finally:
        default_logger.success(f'You should see a "hello-world.html" opened in your browser, '
                               f'if not you may open {url_html_path} manually')

    colored_url = colored('https://opensource.jina.ai', color='cyan', attrs='underline')
    default_logger.success(
        f'🤩 Intrigued? Play with "jina hello-world --help" and learn more about Jina at {colored_url}')


def load_mnist(path):
    with gzip.open(path, 'rb') as fp:
        return np.frombuffer(fp.read(), dtype=np.uint8, offset=16).reshape([-1, 784])

def load_labels(path):
    with gzip.open(path, 'rb') as fp:
        labels = np.frombuffer(fp.read(), dtype=np.uint8, offset=16).reshape([-1, 1])
        return labels

def download_data(targets, download_proxy=None):
    opener = urllib.request.build_opener()
    if download_proxy:
        proxy = urllib.request.ProxyHandler({'http': download_proxy, 'https': download_proxy})
        opener.add_handler(proxy)
    urllib.request.install_opener(opener)
    with ProgressBar(task_name='download fashion-mnist', batch_unit='') as t:
        for v in targets.values():
            if not os.path.exists(v['filename']):
                urllib.request.urlretrieve(v['url'], v['filename'], reporthook=lambda *x: t.update(1))
            if v['filename'] == './workspace/labels-original':
                v['data'] = load_labels(v['filename'])
            else:
                v['data'] = load_mnist(v['filename'])


def index():
    for j in range(num_docs):
        d = jina_pb2.Document()
        d.embedding.CopyFrom(array2pb(targets['index']['data'][j]))
        label = (targets['labels']['data'][j]).item()
        d.tags.update({'id': label})
        index_docs.append(d)

    f = Flow.load_config('flow-index.yml')
    with f:
        f.index(index_docs)


def query():
    # now load query flow from another YAML file
    f = Flow.load_config('flow-query.yml')
    # run it!
    with f:
        f.search_ndarray(targets['query']['data'], shuffle=True, size=128,
                         output_fn=print_result, batch_size=32)
    # write result to html
    write_html(os.path.join('./workspace', 'hello-world.html'))


def config():
    parallel = 2 if sys.argv[1] == 'index' else 1
    shards = 8
    os.environ['RESOURCE_DIR'] = resource_filename('jina', 'resources')
    os.environ['SHARDS'] = str(shards)
    os.environ['PARALLEL'] = str(parallel)
    os.environ['HW_WORKDIR'] = './workspace'
    os.makedirs(os.environ['HW_WORKDIR'], exist_ok=True)
    os.environ['JINA_PORT'] = os.environ.get('JINA_PORT', str(45678))


if __name__ == '__main__':
    targets = {
        'index': {
            'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/train-images-idx3-ubyte.gz',
            'filename': os.path.join('./workspace', 'index-original')
        },
        'query': {
            'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/t10k-images-idx3-ubyte.gz',
            'filename': os.path.join('./workspace', 'query-original')
        },
        'labels': {
            'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/train-labels-idx1-ubyte.gz',
            'filename': os.path.join('./workspace', 'labels-original')
        }
    }
    download_data(targets, None)
    config()

    if len(sys.argv) < 2:
        print('choose between "index" and "search" mode')
        exit(1)
    if sys.argv[1] == 'index':
        config()
        index()
    elif sys.argv[1] == 'query':
        config()
        query()
    else:
        raise NotImplementedError(f'unsupported mode {sys.argv[1]}')
