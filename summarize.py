#!/usr/bin/env python
"""
test.py - initial attempt at automating dn flows using luigi
"""

from collections import Counter
import csv
import hashlib
import json
import logging
import os
import time
from urllib.parse import urlparse

import imagehash
from jinja2 import Environment, PackageLoader
import luigi
import networkx as nx
from PIL import Image
import requests

import twarc

logging.getLogger().setLevel(logging.DEBUG)


def time_hash(digits=6):
    """Generate an arbitrary hash based on the current time for filenames."""
    hash = hashlib.sha1()
    hash.update(str(time.time()).encode())
    t = time.localtime()
    dt = '%s%02d%02d%02d%02d' % (t.tm_year, t.tm_mon, t.tm_mday,
                                 t.tm_hour, t.tm_min)
    return '%s-%s' % (dt, hash.hexdigest()[:digits])


def localstrftime():
    return time.strftime('%Y-%m-%dT%H%M', time.localtime())


def url_filename(url):
    """Given a full URL, return just the filename after the last slash."""
    parsed_url = urlparse(url)
    fname = parsed_url.path.split('/')[-1]
    return fname


def generate_md5(fname, block_size=2**16):
    m = hashlib.md5()
    with open(fname, 'rb') as f:
        while True:
            buf = f.read(block_size)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()


class Twarcy(object):

    _c_key = os.environ.get('CONSUMER_KEY')
    _c_secret = os.environ.get('CONSUMER_SECRET')
    _a_token = os.environ.get('ACCESS_TOKEN')
    _a_token_secret = os.environ.get('ACCESS_TOKEN_SECRET')
    _twarc = twarc.Twarc(consumer_key=_c_key,
                         consumer_secret=_c_secret,
                         access_token=_a_token,
                         access_token_secret=_a_token_secret)


class TestTask(luigi.Task):
    x = luigi.IntParameter()
    y = luigi.IntParameter()

    def run(self):
        print(self.x + self.y)


class FetchTweets(luigi.Task, Twarcy):
    name = luigi.Parameter()
    term = luigi.Parameter()
    lang = luigi.Parameter(default='en')
    count = luigi.IntParameter(default=5000)

    def output(self):
        fname = 'data/%s/tweets.json' % self.name
        return luigi.LocalTarget(fname)

    def run(self):
        i = 0
        tweets = []
        for tweet in self._twarc.search(self.term, lang=self.lang):
            i += 1
            if i > self.count:
                break
            tweets.append(tweet)

        with self.output().open('w') as fp_out:
            for tweet in tweets:
                fp_out.write(json.dumps(tweet) + '\n')


class CountHashtags(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'count-hashtags.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        c = Counter()
        for tweet_str in self.input().open('r'):
            tweet = json.loads(tweet_str)
            c.update([ht['text'].lower()
                      for ht in tweet['entities']['hashtags']])
        with self.output().open('w') as fp_counts:
            writer = csv.DictWriter(fp_counts, delimiter=',',
                                    quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=['hashtag', 'count'])
            writer.writeheader()
            for ht, count in c.items():
                writer.writerow({'hashtag': ht, 'count': count})


class EdgelistHashtags(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'edgelist-hashtags.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        """Each edge is a tuple containing (screen_name, mentioned_hashtag)"""
        with self.output().open('w') as fp_csv:
            writer = csv.DictWriter(fp_csv, delimiter=',',
                                    quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=['user', 'hashtag'])
            writer.writeheader()
            for tweet_str in self.input().open('r'):
                tweet = json.loads(tweet_str)
                for ht in tweet['entities']['hashtags']:
                    writer.writerow({'user': tweet['user']['screen_name'],
                                     'hashtag': ht['text'].lower()})


class CountUrls(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'count-urls.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        c = Counter()
        for tweet_str in self.input().open('r'):
            tweet = json.loads(tweet_str)
            c.update([url['expanded_url'].lower()
                      for url in tweet['entities']['urls']])
        with self.output().open('w') as fp_counts:
            writer = csv.DictWriter(fp_counts, delimiter=',',
                                    quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=['url', 'count'])
            writer.writeheader()
            for url, count in c.items():
                writer.writerow({'url': url, 'count': count})


class CountDomains(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'count-domains.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        c = Counter()
        for tweet_str in self.input().open('r'):
            tweet = json.loads(tweet_str)
            c.update([urlparse(url['expanded_url']).netloc.lower()
                      for url in tweet['entities']['urls']])
        with self.output().open('w') as fp_counts:
            writer = csv.DictWriter(fp_counts, delimiter=',',
                                    quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=['url', 'count'])
            writer.writeheader()
            for url, count in c.items():
                writer.writerow({'url': url, 'count': count})


class CountMentions(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'count-mentions.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        c = Counter()
        for tweet_str in self.input().open('r'):
            tweet = json.loads(tweet_str)
            c.update([m['screen_name'].lower()
                     for m in tweet['entities']['user_mentions']])
        with self.output().open('w') as fp_counts:
            writer = csv.DictWriter(fp_counts, delimiter=',',
                                    quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=['screen_name', 'count'])
            writer.writeheader()
            for screen_name, count in c.items():
                writer.writerow({'screen_name': screen_name,
                                 'count': count})


class EdgelistMentions(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'edgelist-mentions.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        """Each edge is a tuple containing (screen_name,
        mentioned_screen_name)"""
        with self.output().open('w') as fp_csv:
            writer = csv.DictWriter(fp_csv, delimiter=',',
                                    fieldnames=('from_user', 'to_user'))
            writer.writeheader()
            for tweet_str in self.input().open('r'):
                tweet = json.loads(tweet_str)
                for mention in tweet['entities']['user_mentions']:
                    writer.writerow({'from_user': tweet['user']['screen_name'],
                                     'to_user': mention['screen_name']})


class CountMedia(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'count-media.csv')
        return luigi.LocalTarget(fname)

    def run(self):
        c = Counter()
        for tweet_str in self.input().open('r'):
            tweet = json.loads(tweet_str)
            c.update([m['media_url']
                     for m in tweet['entities'].get('media', [])
                     if m['type'] == 'photo'])
        with self.output().open('w') as fp_counts:
            writer = csv.DictWriter(fp_counts, delimiter=',',
                                    quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=['url', 'file', 'count'])
            writer.writeheader()
            for url, count in c.items():
                writer.writerow({'url': url, 'file': url_filename(url),
                                 'count': count})


class FetchMedia(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return CountMedia(name=self.name, term=self.term)

    def output(self):
        # ensure only one successful fetch for each url
        # unless FetchTweets is called again with a new hash
        fname = self.input().fn.replace('count-media.csv',
                                        'media-checksums-md5.txt')
        return luigi.LocalTarget(fname)

    def run(self):
        dirname = 'data/%s/media' % self.name
        os.makedirs(dirname, exist_ok=True)
        # lots of hits to same server, so pool connections
        hashes = []
        session = requests.Session()
        with self.input().open('r') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')
            for row in reader:
                fname = url_filename(row['url'])
                if len(fname) == 0:
                    continue
                r = session.get(row['url'])
                if r.ok:
                    full_name = '%s/%s' % (dirname, fname)
                    with open(full_name, 'wb') as media_file:
                        media_file.write(r.content)
                    md5 = generate_md5(full_name)
        with self.output().open('w') as f:
            for md5, h in hashes:
                f.write('%s %s\n' % (md5, h))


class MatchMedia(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchMedia(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('media-checksums-md5.txt',
                                        'media-graph.json')
        return luigi.LocalTarget(fname)

    def run(self):
        files = sorted(os.listdir('data/%s/media' % self.name))
        hashes = {}
        matches = []
        g = nx.Graph()
        for i in range(len(files)):
            f = files[i]
            fn = 'data/%s/media/%s' % (self.name, f)
            ahash = imagehash.average_hash(Image.open(fn))
            dhash = imagehash.dhash(Image.open(fn))
            phash = imagehash.phash(Image.open(fn))
            hashes[f] = {'ahash': ahash, 'dhash': dhash, 'phash': phash}
            for j in range(0, i):
                f2name = files[j]
                f2 = hashes[f2name]
                sumhash = sum([ahash - f2['ahash'],
                               dhash - f2['dhash'],
                               phash - f2['phash']])
                if sumhash <= 40:
                    matches.append([f, files[j],
                                    ahash - f2['ahash'],
                                    dhash - f2['dhash'],
                                    phash - f2['phash'],
                                    sumhash])
                    g.add_edge(f, f2name)
        with self.output().open('w') as fp_graph:
            components = list(nx.connected_components(g))
            # Note: sets are not JSON serializable
            d = []
            for s in components:
                d.append(list(s))
            logging.debug(' - = - = - = GRAPH HERE - = - = - = -')
            logging.debug(d)
            json.dump(d, fp_graph, indent=2)
        # with self.output().open('w') as fp:
        #    writer = csv.writer(fp, delimiter=',',
        #                        quoting=csv.QUOTE_MINIMAL)
        #    writer.writerow(['file1', 'file2', 'ahash', 'dhash',
        #                     'phash', 'sumhash'])
        #    for match in matches:
        #        writer.writerow(match)


class SummaryHTML(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = 'data/%s/summary.html' % self.name
        return luigi.LocalTarget(fname)

    def run(self):
        env = Environment(loader=PackageLoader('web'))
        t = env.get_template('summary.html')
        title = 'Summary for search "%s"' % self.term
        t.stream(title=title).dump(self.output().fn)


class SummaryJSON(luigi.Task):
    name = luigi.Parameter()
    term = luigi.Parameter()

    def requires(self):
        return FetchTweets(name=self.name, term=self.term)

    def output(self):
        fname = self.input().fn.replace('tweets.json', 'summary.json')
        return luigi.LocalTarget(fname)

    def run(self):
        c = Counter()
        num_tweets = 0
        for tweet_str in self.input().open('r'):
            num_tweets += 1
            tweet = json.loads(tweet_str)
            c.update([m['media_url']
                     for m in tweet['entities'].get('media', [])
                     if m['type'] == 'photo'])
        summary = {
                'path': self.name,
                'date': time.strftime('%Y-%m-%d %H:%M:%S',
                                      time.localtime()),
                'num_tweets': num_tweets,
                'term': self.term
                }
        with self.output().open('w') as fp_summary:
            json.dump(summary, fp_summary)


class RunFlow(luigi.Task):
    name = time_hash()
    term = luigi.Parameter()
    # lang = luigi.Parameter(default='en')
    # count = luigi.IntParameter(default=200)

    def requires(self):
        return CountHashtags(name=self.name, term=self.term), \
            SummaryHTML(name=self.name, term=self.term), \
            SummaryJSON(name=self.name, term=self.term), \
            EdgelistHashtags(name=self.name, term=self.term), \
            CountUrls(name=self.name, term=self.term), \
            CountDomains(name=self.name, term=self.term), \
            CountMentions(name=self.name, term=self.term), \
            EdgelistMentions(name=self.name, term=self.term), \
            MatchMedia(name=self.name, term=self.term)