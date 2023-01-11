#!/usr/bin/python3
import os
from git import Repo

repo_path = "/var/www/blog"

repo = Repo(repo_path)
origin = repo.remotes[0]
origin.pull()

os.environ['GEM_HOME'] = '/home/qyzhang/gems'
os.environ['PATH'] += os.pathsep + '/home/qyzhang/gems/bin'

os.chdir(repo_path)
os.putenv('JEKYLL_ENV', 'production')
os.system("bundle exec jekyll b")

print("Content-type: text/plain")
print("")
print("Success")
