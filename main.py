# -*- coding: utf-8 -*-
import argparse
import os

from marko.ext.gfm import gfm as marko
from github import Github
from feedgen.feed import FeedGenerator
from lxml.etree import CDATA

MD_HEAD = """**<p align="center">[Leeyom's Blog](https://blog.leeyom.top)</p>**
====

**<p align="center">用于记录一些幼稚的想法和脑残的瞬间</p>**
[![](https://user-images.githubusercontent.com/22115219/149507985-22e22223-4644-47bf-abf9-c388c287cc38.JPEG)](https://blog.leeyom.top)

## 联系方式
- Twitter：[@super_leeyom](https://twitter.com/super_leeyom)
- Telegram：[@super_leeyom](https://t.me/super_leeyom)
- Email：[leeyomwang@163.com](mailto:leeyomwang@163.com)
- Blog：[https://blog.leeyom.top](https://blog.leeyom.top)
- RSS：[RSS Feed](https://raw.githubusercontent.com/{repo_name}/master/feed.xml)
"""

BACKUP_DIR = "backup"
ANCHOR_NUMBER = 5
TOP_ISSUES_LABELS = ["Top"]
TODO_ISSUES_LABELS = ["TODO"]
IGNORE_LABELS = TOP_ISSUES_LABELS + TODO_ISSUES_LABELS


def get_me(user):
    return user.get_user().login


def is_me(issue, me):
    return issue.user.login == me


def is_hearted_by_me(comment, me):
    reactions = list(comment.get_reactions())
    for r in reactions:
        if r.content == "heart" and r.user.login == me:
            return True
    return False


# help to covert xml vaild string
def _valid_xml_char_ordinal(c):
    codepoint = ord(c)
    # conditions ordered by presumed frequency
    return (
            0x20 <= codepoint <= 0xD7FF
            or codepoint in (0x9, 0xA, 0xD)
            or 0xE000 <= codepoint <= 0xFFFD
            or 0x10000 <= codepoint <= 0x10FFFF
    )


def format_time(time):
    return str(time)[:10]


def login(token):
    return Github(token)


def get_repo(user: Github, repo: str):
    return user.get_repo(repo)


def parse_TODO(issue):
    body = issue.body.splitlines()
    todo_undone = [l for l in body if l.startswith("- [ ] ")]
    todo_done = [l for l in body if l.startswith("- [x] ")]
    # just add info all done
    if not todo_undone:
        return f"[{issue.title}]({issue.html_url}) all done", []
    return (
        f"[{issue.title}]({issue.html_url})--{len(todo_undone)} jobs to do--{len(todo_done)} jobs done",
        todo_done + todo_undone,
    )


def get_top_issues(repo):
    return repo.get_issues(labels=TOP_ISSUES_LABELS)


def get_todo_issues(repo):
    return repo.get_issues(labels=TODO_ISSUES_LABELS)


def get_repo_labels(repo):
    return [l for l in repo.get_labels()]


def get_issues_from_label(repo, label):
    return repo.get_issues(labels=(label,))


def add_issue_info(issue, md):
    time = format_time(issue.created_at)
    md.write(f"- [{issue.title}]({issue.html_url})--{time}\n")


def add_md_todo(repo, md, me):
    todo_issues = list(get_todo_issues(repo))
    if not TODO_ISSUES_LABELS or not todo_issues:
        return
    with open(md, "a+", encoding="utf-8") as md:
        md.write("## TODO\n")
        for issue in todo_issues:
            if is_me(issue, me):
                todo_title, todo_list = parse_TODO(issue)
                md.write("TODO list from " + todo_title + "\n")
                for t in todo_list:
                    md.write(t + "\n")
                # new line
                md.write("\n")


def add_md_top(repo, md, me):
    top_issues = list(get_top_issues(repo))
    if not TOP_ISSUES_LABELS or not top_issues:
        return
    with open(md, "a+", encoding="utf-8") as md:
        md.write("## 置顶文章\n")
        for issue in top_issues:
            if is_me(issue, me):
                add_issue_info(issue, md)


def add_md_recent(repo, md, me, limit=5):
    count = 0
    with open(md, "a+", encoding="utf-8") as md:
        # one the issue that only one issue and delete (pyGitHub raise an exception)
        try:
            md.write("## 最近更新\n")
            for issue in repo.get_issues():
                if is_me(issue, me):
                    add_issue_info(issue, md)
                    count += 1
                    if count >= limit:
                        break
        except:
            return


def add_md_header(md, repo_name):
    with open(md, "w", encoding="utf-8") as md:
        md.write(MD_HEAD.format(repo_name=repo_name))


def add_md_label(repo, md, me):
    labels = get_repo_labels(repo)
    with open(md, "a+", encoding="utf-8") as md:
        for label in labels:

            # we don't need add top label again
            if label.name in IGNORE_LABELS:
                continue

            issues = get_issues_from_label(repo, label)
            if issues.totalCount:
                md.write("## " + label.name + "\n")
                issues = sorted(issues, key=lambda x: x.created_at, reverse=True)
            i = 0
            for issue in issues:
                if not issue:
                    continue
                if is_me(issue, me):
                    if i == ANCHOR_NUMBER:
                        md.write("<details><summary>显示更多</summary>\n")
                        md.write("\n")
                    add_issue_info(issue, md)
                    i += 1
            if i > ANCHOR_NUMBER:
                md.write("</details>\n")
                md.write("\n")


def get_to_generate_issues(repo, dir_name, issue_number=None):
    md_files = os.listdir(dir_name)
    generated_issues_numbers = [
        int(i.split("_")[0]) for i in md_files if i.split("_")[0].isdigit()
    ]
    to_generate_issues = [
        i
        for i in list(repo.get_issues())
        if int(i.number) not in generated_issues_numbers
    ]
    if issue_number:
        to_generate_issues.append(repo.get_issue(int(issue_number)))
    return to_generate_issues


def generate_rss_feed(repo, filename, me):
    generator = FeedGenerator()
    generator.id(repo.html_url)
    generator.title(f"RSS feed of {repo.owner.login}'s {repo.name}")
    generator.author(
        {"name": os.getenv("GITHUB_NAME"), "email": os.getenv("GITHUB_EMAIL")}
    )
    generator.link(href=repo.html_url)
    generator.link(
        href=f"https://raw.githubusercontent.com/{repo.full_name}/master/{filename}",
        rel="self",
    )
    for issue in repo.get_issues():
        if not issue.body or not is_me(issue, me) or issue.pull_request:
            continue
        item = generator.add_entry(order="append")
        item.id(issue.html_url)
        item.link(href=issue.html_url)
        item.title(issue.title)
        item.published(issue.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"))
        for label in issue.labels:
            item.category({"term": label.name})
        body = "".join(c for c in issue.body if _valid_xml_char_ordinal(c))
        item.content(CDATA(marko.convert(body)), type="html")
    generator.atom_file(filename)


def main(token, repo_name, issue_number=None, dir_name=BACKUP_DIR):
    user = login(token)
    me = get_me(user)
    repo = get_repo(user, repo_name)
    # add to readme one by one, change order here
    add_md_header("README.md", repo_name)
    for func in [add_md_top, add_md_recent, add_md_label, add_md_todo]:
        func(repo, "README.md", me)

    generate_rss_feed(repo, "feed.xml", me)
    to_generate_issues = get_to_generate_issues(repo, dir_name, issue_number)

    # save md files to backup folder
    for issue in to_generate_issues:
        save_issue(issue, me, dir_name)


def save_issue(issue, me, dir_name=BACKUP_DIR):
    md_name = os.path.join(
        dir_name, f"{issue.number}_{issue.title.replace(' ', '.')}.md"
    )
    with open(md_name, "w") as f:
        f.write(f"# [{issue.title}]({issue.html_url})\n\n")
        f.write(issue.body)
        if issue.comments:
            for c in issue.get_comments():
                if is_me(c, me):
                    f.write("\n\n---\n\n")
                    f.write(c.body)


if __name__ == "__main__":
    if not os.path.exists(BACKUP_DIR):
        os.mkdir(BACKUP_DIR)
    parser = argparse.ArgumentParser()
    parser.add_argument("github_token", help="github_token")
    parser.add_argument("repo_name", help="repo_name")
    parser.add_argument(
        "--issue_number", help="issue_number", default=None, required=False
    )
    options = parser.parse_args()
    main(options.github_token, options.repo_name, options.issue_number)