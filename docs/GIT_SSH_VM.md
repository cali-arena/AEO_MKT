# Push from VM without username/password (SSH)

Use SSH so `git push` never asks for username or password.

## 1. On the VM: create an SSH key (if you don’t have one)

```bash
ssh-keygen -t ed25519 -C "lucas.cabralf@icloud.com" -f ~/.ssh/id_ed25519_github -N ""
```

- `-N ""` = no passphrase (optional; use a passphrase if you prefer).
- This creates `~/.ssh/id_ed25519_github` (private) and `~/.ssh/id_ed25519_github.pub` (public).

## 2. Add the public key to GitHub

```bash
cat ~/.ssh/id_ed25519_github.pub
```

Copy the whole line (starts with `ssh-ed25519`).

Then:

1. Open **GitHub** → **Settings** → **SSH and GPG keys**  
   (or https://github.com/settings/keys)
2. **New SSH key**
3. Title: e.g. `AEO_MKT VM (ubuntu-16gb-hel1-1)`
4. Key type: **Authentication Key**
5. Paste the copied line → **Add SSH key**

## 3. On the VM: use SSH for GitHub

```bash
# Use this host with your key
cat >> ~/.ssh/config << 'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_github
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

## 4. On the VM: switch remote to SSH and push

From the repo on the VM:

```bash
cd /root/AEO_MKT
git remote set-url origin git@github.com:cali-arena/AEO_MKT.git
git remote -v
git push origin main
```

No username or password prompt; the SSH key is used automatically.

---

**One-time test:** `ssh -T git@github.com`  
You should see: `Hi cali-arena! You've successfully authenticated...`
