# QUICKSTART — connect your skills box in 7 steps

Run all of this on YOUR Ubuntu box (4 GB RAM is enough).
After step 5 you have a global URL that works from anywhere in the world.

## 1) Unzip + install (one command, ~10-20 min mostly torch download)

    mkdir ~/parwa-box && cd ~/parwa-box
    unzip ~/Downloads/parwa-skills-box.zip
    bash setup_skills_box.sh

This copies the service to `~/skills-box`, makes a venv, installs deps,
pre-downloads models, and installs cloudflared.

## 2) Start the box

    cd ~/skills-box
    nohup ./start.sh > box.log 2>&1 &

Check it is alive:

    curl http://localhost:8055/health

You should see `"ok": true` plus a live RAM report.

## 3) Get your key

    cat ~/skills-box/.skills_key

(Generated on first start. Keep it secret — it unlocks all skills.)

## 4) Open a global tunnel

    cloudflared tunnel --url http://localhost:8055

Copy the `https://xxxx-xxxx.trycloudflare.com` URL it prints.

## 5) Prove it works from OUTSIDE (use your phone, or any machine)

    curl https://xxxx-xxxx.trycloudflare.com/health

    curl -X POST https://xxxx-xxxx.trycloudflare.com/classify \
      -H "X-Skills-Key: YOUR_KEY" \
      -H "Content-Type: application/json" \
      -d '{"text":"where is my order? it has been 10 days","labels":["shipping_delay","refund","other"]}'

Expect `{"ok":true,"data":{...,"label":"shipping_delay",...}}`.

## 6) (Optional) pin a permanent name

Quick-tunnel URLs change on restart. For a permanent one:

    cloudflared tunnel login
    cloudflared tunnel create skills
    cloudflared tunnel route dns skills skills.parwa.buzz
    cloudflared tunnel run --url http://localhost:8055 skills

Now `https://skills.parwa.buzz` is your box, forever. Run it as a systemd
service so it survives reboots (README has the pattern).

## 7) Point your Render backend at it

Set these env vars on Render, then redeploy:

    SKILLS_BOX_URL=https://skills.parwa.buzz
    SKILLS_BOX_KEY=your_key_from_step_3
    OSS_SKILLS_BOX=1

## Optional: /remember in the cloud (zero local disk)

Create a free Supabase Postgres, then in `~/skills-box/skills.env`:

    SKILLS_MEM_STORE=postgres
    SKILLS_MEM_DB_URL=postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres

Restart the box. Done — memory lives in Supabase's free tier.

---

Notes:
- If the box is ever DOWN, tickets still work — the backend falls back to
  its local regex/classifier. Box down is never ticket down.
- `/browse` is the only stub (501) until the LLM-brain decision.
- Full reference: `mini-services/skills-box/README.md` inside this zip.
