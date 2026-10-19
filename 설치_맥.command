#!/bin/bash
cd "$(dirname "$0")"
echo "============================================"
echo "  체험단 후기 자동화 설치 (맥) - 처음 한 번만"
echo "============================================"
python3 --version || { echo "[!] 파이썬이 없습니다. 화면에 뜨는 '설치'를 누른 뒤 이 파일을 다시 여세요."; read -p "엔터"; exit 1; }
echo "[1/4] 파이썬 확인 완료"
echo "[2/4] 필요한 부품 설치 중..."
python3 -m pip install --user --quiet playwright requests pillow || echo "    (부품 설치 경고 - 맥은 에고라이트를 쓰니 그대로 진행합니다)"
echo "[3/4] 클로드 코드 확인 중..."
command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ] || curl -fsSL https://claude.ai/install.sh | bash
echo "[4/4] 에고라이트 확인 (사진 받기와 임시저장은 에고라이트로 합니다)"
if [ -d "/Applications/ego lite.app" ] || [ -d "$HOME/Applications/ego lite.app" ]; then
  echo "    에고라이트 있음. 에고라이트를 열고 '체험단 블로그 아이디'로 네이버에 직접 로그인해 두세요."
else
  echo "    에고라이트가 없습니다. 열리는 페이지에서 내려받아 설치 -> 앱을 한 번 열어 첫 화면을 끝내 주세요."
  open "https://lite.ego.app/"
fi
echo "============================================"
echo "  설치 완료!"
echo "  1. 내정보.txt 를 열어 체험단 블로그ID 채우기"
echo "  2. 체험단시작_맥.command 더블클릭"
echo "============================================"
read -p "엔터를 누르면 닫힙니다"
