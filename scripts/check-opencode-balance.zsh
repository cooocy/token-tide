#!/bin/zsh
set -euo pipefail

# 在这里粘贴完整 Cookie：auth=... 或 __Host-auth=...
# 安全提示：执行完请恢复为占位符，不要提交真实 Cookie。
OPENCODE_COOKIE='auth=请替换这里'

# 多个 Workspace 时可以手动填写 wrk_...；留空则自动选择第一个。
OPENCODE_WORKSPACE_ID='wrk_01KSD0330DG1N1GDSVR6NZXKCE'

WORKSPACES_RPC_ID='def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f'
BILLING_RPC_ID='c83b78a614689c38ebee981f9b39a8b377716db85c1fd7dbab604adc02d3313d'
BASE_URL='https://opencode.ai'

if [[ "$OPENCODE_COOKIE" == *'请替换这里'* || -z "$OPENCODE_COOKIE" ]]; then
  echo '错误：请先在脚本顶部填写 OPENCODE_COOKIE。' >&2
  exit 1
fi

if [[ "$OPENCODE_COOKIE" != auth=* && "$OPENCODE_COOKIE" != __Host-auth=* ]]; then
  echo '错误：Cookie 应为 auth=... 或 __Host-auth=...' >&2
  exit 1
fi

if [[ -z "$OPENCODE_WORKSPACE_ID" ]]; then
  echo '正在查询 Workspace...'

  workspace_response="$(
    curl --fail-with-body --silent --show-error --get \
      "${BASE_URL}/_server" \
      --max-time 20 \
      --data-urlencode "id=${WORKSPACES_RPC_ID}" \
      -H "Cookie: ${OPENCODE_COOKIE}" \
      -H "X-Server-Id: ${WORKSPACES_RPC_ID}" \
      -H "X-Server-Instance: server-fn:manual-$(date +%s)" \
      -H "Origin: ${BASE_URL}" \
      -H "Referer: ${BASE_URL}" \
      -H 'Accept: text/javascript, application/json;q=0.9, */*;q=0.8' \
      -H 'User-Agent: Mozilla/5.0'
  )"

  OPENCODE_WORKSPACE_ID="$(
    printf '%s' "$workspace_response" |
      perl -0777 -ne 'if (/(wrk_[A-Za-z0-9]+)/) { print $1 }'
  )"

  if [[ -z "$OPENCODE_WORKSPACE_ID" ]]; then
    echo '错误：未识别到 Workspace。Cookie 可能已失效。' >&2
    echo '也可以在脚本顶部手动填写 OPENCODE_WORKSPACE_ID。' >&2
    exit 1
  fi
fi

echo "Workspace: ${OPENCODE_WORKSPACE_ID}"
echo '正在查询 Zen 余额...'

billing_response="$(
  curl --fail-with-body --silent --show-error --get \
    "${BASE_URL}/_server" \
    --max-time 20 \
    --data-urlencode "id=${BILLING_RPC_ID}" \
    --data-urlencode "args=[\"${OPENCODE_WORKSPACE_ID}\"]" \
    -H "Cookie: ${OPENCODE_COOKIE}" \
    -H "X-Server-Id: ${BILLING_RPC_ID}" \
    -H "X-Server-Instance: server-fn:manual-$(date +%s)" \
    -H "Origin: ${BASE_URL}" \
    -H "Referer: ${BASE_URL}/workspace/${OPENCODE_WORKSPACE_ID}" \
    -H 'Accept: text/javascript, application/json;q=0.9, */*;q=0.8' \
    -H 'User-Agent: Mozilla/5.0'
)"

raw_balance="$(
  printf '%s' "$billing_response" |
    perl -0777 -ne '
      if (
        /(?:"customerID"|customerID)\s*:/ &&
        /(?:"balance"|balance)\s*:\s*(?:\$R\[\d+\]\s*=\s*)?(-?\d+(?:\.\d+)?)/
      ) {
        print $1
      }
    '
)"

if [[ -z "$raw_balance" ]]; then
  echo '错误：请求成功，但未能从响应中解析余额。' >&2
  echo '内部 RPC 格式可能已发生变化。' >&2
  exit 1
fi

awk -v value="$raw_balance" \
  'BEGIN { printf "OpenCode Zen balance: $%.2f USD\n", value / 100000000 }'
