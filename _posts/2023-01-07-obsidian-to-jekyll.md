---
categories:
- DevOps
date: 2023-01-07 10:31:46 +0800
last_modified_at: 2023-01-13 18:45:23 +0800
tags:
- linux
- devops
- jekyll
title: Obsidian 笔记自动转换为 Jekyll 博客
---

## 前言

之前一直想搭一个博客，搭了几次但一篇文章没写过🙃，最近在使用了 [Obsidian](https://obsidian.md/) 作为自己的个人笔记后感觉一些笔记内容可以直接写到博客里，但是直接把 Obsidian 中的 md 文件作为 [Jekyll](https://jekyllrb.com/) 博客的博文还是会有一些问题，所以就想着写一个脚本能够自动地转换 md 文件并且能够自动部署。折腾了半天最终可以实现一键转换和部署，其执行流程如下：

1. 在 Obsidian 笔记中用 md 写笔记
2. 挑选哪些笔记是可以作为博文的，将其添加进 Posts 笔记中
3. 运行 python 脚本，将对应的笔记转换成 Jekyll 博文并保存在本地的 Jekyll 仓库中
4. Python 脚本会将本地的 Jekyll 仓库推送到 github/gitee
5. Github/Gitee 中收到 push 后会访问 webhook URL
6. 服务器 nginx 收到 webhook 请求，调用用于部署的 python 脚本
7. 服务器 python 脚本拉取 github/gitee 的 Jekyll 仓库到本地
8. 服务器 python 脚本执行 Jekyll build

这样在写好博文后就只需要运行本地的 python 脚本就可以完成整个转换和部署流程。

## Chiripy 主题

该方案有许多内容都是与 Jekyll 的 [Chirpy](https://github.com/cotes2020/jekyll-theme-chirpy) 主题相关的，包括 python 脚本中的代码。若要使用其他主题请相应地进行修改。

## 将 Obsidian 笔记转换为 Jekyll 博文

Obsidian 笔记和 Jekyll 博文一样都是使用的 markdown 进行编写，但两者所使用的一些自定义语法不同，Jekyll 所需的 frontmatter 也不同。另外 Obsidian 笔记更偏向个人记录，可能一些内容不适合在博文中出现，所以需要有一个办法能够既保持 Obsidian 笔记的个人内容又能自动地在博文中去掉或转换这些内容。为此，编写了一个 python 脚本来自动化该过程，该脚本可在 [github gist](https://gist.github.com/cs-qyzhang/9ae9f68f91e6c853ce6911f07eddf168) 下载。下面介绍该脚本的设计。

### 使用 `Posts` 笔记保存元数据

为了能够指定哪些 Obsidian 笔记转换为博文而又不更改原来笔记的内容，选择使用一个单独的笔记文件记录哪些笔记要转化为博文以及转化过程中需要使用的信息。下面是该 `Posts` 笔记的示例：

~~~markdown
## [[Disk Recovery]]

```yaml
title: Linux 硬盘恢复
categories: [DevOps]
tags: [linux,devops]
```

```python
import re
content = content.replace("钟XX", "某同学")
content = content.replace("个人碎碎念", "")
content = re.sub(r"[\w\.-]+@([\w-]+)\.com", r"https://\g<1>.com", content)
```

## [[GEM5]]

```yaml
title: GEM5 环境配置
categories: [Computer Architecture,Simulator]
tags: [linux,gem5]
```
~~~

从示例中能够看到，每个博文使用了一个二级标题，这里博文采用了 Obsidian 的 wikilinkws 语法来引用另一个笔记文件。每个博文的二级标题下面可以有两个代码块：一个 yaml 的代码块以及一个 python 的代码块。其中 yaml 的代码块是对应 Jekyll 博文的 frontmatter，这样就可以避免在 Obsidian 笔记中直接添加对应的与 Jekyll 有关的 frontmatter。而 python 代码块则是可以利用 python 的 `exec()` 在运行时注入并执行与该博文相关的 python 代码。Python 脚本把对应笔记的文本内容字符串放在了 `content` 变量中，在 python 代码块中就可以对 `content` 进行处理，比如这里的 Disk Recovery 笔记就把包含隐私的姓名替换，把不适合放在博文中的内容去掉，并且还给了一个使用 `re` 模块处理文本的示例。

在 python 脚本中，为了解析 Posts 文件，使用了 [markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/) 包。该包可以将 md 文件解析成诸如 heading、code fence 等 nodes。

### 博文日期

Jekyll 可以在 frontmatter 中指定博文的发表日期和修改日期，这里在 python 脚本中通过获取 Obsidian 笔记文件的 `ctime` 和 `mtime` 来自动地设置笔记日期。

### 图片处理

Obsidian 和 Chirpy 各自有不同的语法来指定图像的大小等内容。Obsidian 在图片的 alt 文本中指定，如 `![xxx](xxx.png){: .normal }{: width="400" height="300" }` 语法指定。所以为了在 Obsidian 中保持 Obsidian 的语法需要在 python 脚本中进行转换。

除此之外，Chirpy 还可以通过下面的语法指定图片的标题：

```markdown
![xxx](xxx.jpg)
_caption_
```

然而在 Obsidian 中目前还不支持添加图片的标题。为了能够在 Jekyll 博文中给图片添加标题，这里选择扩展一下 Obsidian 的指定图片大小的语法，通过在 alt 文本中再添加一个 `|` 来指定标题，如 `![alt](xxx.png){: width="400" .normal }` 就意味着 alt 文本是“alt”，标题为“caption”，图片宽度为 400。需要注意的是要识别一下几种情况：只有 alt，alt+size，alt+caption，alt+size+caption。

### 链接处理

在测试时发现 Jekyll 的 md 渲染器不能识别 `[]()` 链接里中括号内含有 `&#124;` 字符的情况，比如 `[title &#124; subtitle](https://example.com)`，包含 `|` 时无法正常渲染链接，但将 `|` 改为对应的 html 代码 `&#124;` 后即可正常渲染，所以在 python 脚本中还会对这种情况进行处理。

### Callouts 转换为 Prompts

Obsidian 和 Chirpy 都支持如下所示的提示框：

> 这里包含了一些需要注意的事项
{: .prompt-warning }

Obsidian 中将此称为 callouts，使用如下语法：

```markdown
> [!warning]
> 这里包含了一些需要注意的事项
```

而在 Chirpy 中则称为 prompts，使用如下语法：

```markdown
> 这里包含了一些需要注意的事项
{: .prompt-warning }
```

所以需要在 python 脚本中进行转换。

## 自动部署

以上脚本可以将 Obsidian 笔记从对应的 vault 文件夹中读出并转化为 Jekyll 博文保存在本地的 Jekyll 博客仓库中。转换后还需要执行 Jekyll 的部署，为了方便部署可以将该过程自动化。这里利用 github/gitee 仓库的 webhook 来向服务器发起部署请求，这样在本地的 Jekyll 仓库 push 到 github/gitee 上时 github/gitee 就会向指定的 URL 发起一个 POST 请求，服务器的 nginx 收到 http 请求后通过 fcgiwrap 执行用于 Jekyll 部署的 python 脚本，在该脚本中会运行服务器端 Jekyll 博客仓库的 pull 操作以及 Jekyll 的 build 操作。

为了执行 Jekyll 的部署，首先需要在服务器上搭建 Jekyll 环境，具体的搭建方法见 [Jekyll](https://jekyllrb.com/)，这里假设在服务器上已经有了 Jekyll 环境。

用于部署的 python 脚本使用了 [GitPython](https://gitpython.readthedocs.io/en/stable/) 包来执行 git 操作，而 nginx 和 fcgiwrap 使用的 Linux 用户都是 `www-data`，所以使用其他用户进行 `pip install` 是不可以的， `www-data` 会无法识别到 GitPython 包。这里我们使用 `apt` 安装该包。下面是服务器上搭建部署环境的一些命令：

```bash
sudo apt install python3-git # 安装全局的 GitPython 包
sudo apt install fcgiwrap
sudo systemctl enable fcgiwrap
sudo cp -r /home/<yourname>/.ssh /var/www/ # 使 www-data 可以访问 github/gitee
sudo chown www-data:www-data -R /var/www
sudo adduser www-data <yourname> # 使普通用户可以访问 /var/www 下的文件
```

之后我们需要将 Jekyll github/gitee 仓库克隆到 `/var/www/blog` 下。由于该仓库的拉取是由 `www-data` 用户进行的，所以我们需要以 `www-data` 用户执行克隆操作。首先使用命令 `sudo -u www-data /bin/bash` 以 `www-data` 进行登录，之后再执行 `git clone` 操作。

用于部署的 python 脚本如下：

```python
#!/usr/bin/python3
import os
from git import Repo

repo_path = "/var/www/blog"

repo = Repo(repo_path)
origin = repo.remotes[0]
origin.pull()

os.environ['GEM_HOME'] = '/home/<yourname>/gems'
os.environ['PATH'] += os.pathsep + '/home/<yourname>/gems/bin'

os.chdir(repo_path)
os.putenv('JEKYLL_ENV', 'production')
os.system("bundle exec jekyll b")

print("Content-type: text/plain")
print("")
print("Success")
```

Nginx 的配置文件内容如下：

```
server {
    listen 80;
    listen [::]:80;

    server_name jianyue.tech www.jianyue.tech;

    # Enforce HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;

    ssl_certificate         /etc/ssl/nginx/jianyue.tech.crt;
    ssl_certificate_key     /etc/ssl/nginx/jianyue.tech.key;

    root /var/www/blog/_site;
    index index.html index.htm index.nginx-debian.html;
    server_name jianyue.tech www.jianyue.tech;

    location / {
        try_files $uri $uri/ =404;
    }

    location /webhook/blog {
        fastcgi_param   SCRIPT_FILENAME /var/www/webhook.py;
        fastcgi_pass    unix:/var/run/fcgiwrap.socket;
	}
}
```

如果该 python 脚本是从 Windows 直接通过 `scp` 拷贝到服务器上需要注意先将文件的换行符从 CRLF 改为 LF。

## Gitee 仓库

Github 在国内访问经常出现问题，在服务器上拉取 github 的仓库比较麻烦，为了方便服务器的拉取可以在 gitee 上也同时添加一个仓库，并在本地仓库中添加 gitee 和 github 两个 remote，将 webhook 放在 gitee 上，在本地做出修改推送时同时推送两个仓库，在推送到 gitee 仓库时会触发 webhook 来使服务器运行相应的拉取和部署工作。

## Giscus 评论系统

Chirpy 支持 giscus 评论。在 [giscus](https://giscus.app/zh-CN) 中填写相关信息，之后会在该网页的“启用 giscus”一节中显示对应的 html，其中包含了 repo-id 等信息，将这些信息填写在 `_config.yml` 中的 `comments.giscus` 内，并将 `comments.active` 设为 `giscus`。

## Github Pages 转到自定义域名

直接在仓库设置的 Pages 里设置 Custom domain，不需要设置 DNS 的 CNAME 解析，因为设置了 CNAME 解析之后会将自己的域名重定向到 github 的域名，而这样设置后 github 虽然提示 DNS 有问题但在访问对应的 Github Pages 时会产生 301 redirect 请求转到自定义的域名。见 [Redirect Github Pages to custom domain - Stack Overflow](https://stackoverflow.com/a/66601856)。

至此博客的部署工作就完成了，之后就是抽时间总结写博文了🙃