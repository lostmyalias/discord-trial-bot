# usage: ./push.sh "commit message"
#!/bin/bash
git remote set-url origin https://lostmyalias:$GITHUB_TOKEN@github.com/lostmyalias/skyspoofer-trial-bot.git
git add .
git commit -m "$1"
git push
git remote set-url origin https://github.com/lostmyalias/skyspoofer-trial-bot.git

