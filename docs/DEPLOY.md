cd /Users/ncnslks/Downloads/ai_capcut
git add .
git commit -m "第一次全部提交"
git push -u origin main


ssh-keygen -t rsa -b 4096 -C "158253524@qq.com"


git remote set-url origin git@github.com:lengyan11001/ai_capcut.git


CORS_ORIGINS=http://159.75.168.18:8000

curl -X POST "http://159.75.168.18:8000/auth/recharge" \
  -H "Content-Type: application/json" \
  -H "X-Recharge-Token: a975fe7d58299ac456c1eef8649fff0d" \
  -d '{"email": "liux21101@gmail.com", "amount": 5000}'