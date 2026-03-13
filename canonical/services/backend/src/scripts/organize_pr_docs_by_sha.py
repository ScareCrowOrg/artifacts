def load_analyzed_prs(path="pr_analisadas.txt"):
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())

def save_analyzed_pr(pr_number, path="pr_analisadas.txt"):
    with open(path, "a") as f:
        f.write(f"{pr_number}\n")
import os
import requests
from dotenv import load_dotenv
import base64

# Carrega variáveis do .env
load_dotenv()
token = os.getenv("GITHUB_PAT")  # Atualizar para o nome correto do token
owner = "ScareCrowOrg"
repo = "ScareVerseLab"
base_dir = "docs/issues/pull_requests"
headers = {"Authorization": f"Bearer {token}"}

def get_closed_prs(page_limit=1):
    prs = []
    page = 1
    per_page = 50
    while page <= page_limit:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=closed&per_page={per_page}&page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Erro ao buscar PRs fechadas: {response.status_code}, {response.text}")
            break
        batch = response.json()
        if not batch:
            break
        prs.extend(batch)
        page += 1
    return prs

def get_pr_files(pr_number):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    return requests.get(url, headers=headers).json()

def get_commit_sha(pr):
    # Tenta pegar o SHA do merge_commit, se existir
    return pr.get("merge_commit_sha") or pr["head"]["sha"]

def download_md_by_sha(pr_number, sha, filename, dry_run=False):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}?ref={sha}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200 and r.json().get("type") == "file":
        content = r.json()["content"]
        decoded = base64.b64decode(content)
        found_paths = []
        for root, dirs, files in os.walk("."):
            for f in files:
                if f == os.path.basename(filename):
                    found_paths.append(os.path.join(root, f))
        if not found_paths:
            pr_dir = os.path.join(base_dir, str(pr_number))
            local_path = os.path.join(pr_dir, os.path.basename(filename))
            if dry_run:
                print(f"[DRY RUN][PR #{pr_number}] Criaria: {local_path} (destino: {pr_dir}, não existe no repo)")
            else:
                os.makedirs(pr_dir, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(decoded)
                print(f"Salvo: {local_path}")
        else:
            trecho = decoded[:100].decode(errors="ignore")
            match_found = False
            for path in found_paths:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                        if trecho in file_content:
                            if dry_run:
                                print(f"[DRY RUN] Já existe: {path} (conteúdo compatível)")
                            else:
                                print(f"Arquivo já existe: {path}")
                            match_found = True
                            break
                except Exception as e:
                    print(f"Erro ao ler {path}: {e}")
            if not match_found:
                pr_dir = os.path.join(base_dir, str(pr_number))
                local_path = os.path.join(pr_dir, os.path.basename(filename))
                if dry_run:
                    print(f"[DRY RUN][PR #{pr_number}] Criaria: {local_path} (destino: {pr_dir}, nome existe, mas conteúdo diferente)")
                else:
                    os.makedirs(pr_dir, exist_ok=True)
                    with open(local_path, "wb") as f:
                        f.write(decoded)
                    print(f"Salvo: {local_path}")
    else:
        print(f"Arquivo não encontrado via SHA: {filename}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Organiza documentos .md de PRs por SHA")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula, não cria arquivos")
    parser.add_argument("--pages", type=int, default=1, help="Número de páginas de PRs para processar")
    args = parser.parse_args()
    prs = get_closed_prs(page_limit=args.pages)
    analyzed_prs = load_analyzed_prs()
    for pr in prs:
        pr_number = pr["number"]
        if pr_number in analyzed_prs:
            continue  # pula PR já analisada
        sha = get_commit_sha(pr)
        files = get_pr_files(pr_number)
        for file in files:
            filename = file["filename"]
            if filename.endswith(".md"):
                download_md_by_sha(pr_number, sha, filename, dry_run=args.dry_run)
        if not args.dry_run:
            save_analyzed_pr(pr_number)

if __name__ == "__main__":
    main()
