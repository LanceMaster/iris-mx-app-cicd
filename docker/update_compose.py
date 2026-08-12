#!/usr/bin/env python
import os
import sys
from typing import Dict, Any, List, Union

# 디렉토리 경로 
env_path = "./docker"  

# PyYAML 체크
try:
    import yaml
except ImportError:
    print("PyYAML 필요: python3 -m pip install 파일명.whl", file=sys.stderr)
    sys.exit(1)

def load_env_file(env_file: str) -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    with open(env_file, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                key, val = line, ""
            else:
                key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                env_vars[key] = val
    return env_vars

def normalize_env(env_block: Union[Dict[str, Any], List[str], None]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not env_block:
        return result
    if isinstance(env_block, dict):
        for k, v in env_block.items():
            result[str(k)] = "" if v is None else str(v)
    elif isinstance(env_block, list):
        for item in env_block:
            if "=" in item:
                k, v = item.split("=", 1)
                result[k] = v
            else:
                result[item] = ""
    return result

def overlay_env_and_resources(compose: Dict[str, Any], overlay: Dict[str, str]) -> Dict[str, Any]:
        
    services = compose.get("services", {})
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue

        # 1. environment overlay
        current_env = normalize_env(svc.get("environment"))
        for k, v in overlay.items():
            if k not in ("IRIS_CPU_LIMIT", "IRIS_MEMORY_LIMIT"):
                current_env[k] = v
        svc["environment"] = current_env

        # 2. CPU / Memory limits overlay
        cpu_limit = overlay.get("IRIS_CPU_LIMIT")
        mem_limit = overlay.get("IRIS_MEMORY_LIMIT")

        if cpu_limit or mem_limit:
            svc.setdefault("deploy", {}).setdefault("resources", {}).setdefault("limits", {})
            limits = svc["deploy"]["resources"]["limits"]
            if cpu_limit:
                limits["cpus"] = cpu_limit
            if mem_limit:
                limits["memory"] = mem_limit

    compose["services"] = services
    return compose

def override_env_in_compose(compose_file, env_file, output_file):
    # docker-compose.yaml 읽기
    with open(compose_file, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f) or {}

    env_vars = load_env_file(env_file)
    new_compose = overlay_env_and_resources(compose_data, env_vars)
   
    # 결과 저장
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(new_compose, f, sort_keys=False, default_flow_style=False, width=4096, allow_unicode=True)

    print(f"[환경 변수 적용 완료] → {output_file}")


if __name__ == "__main__":
    # 환경에 맞게 선택
    env_mode = os.getenv("MODE", "dev")  # 기본 dev
    env_file = f"{env_path}/{env_mode}/app.{env_mode}.env" 
    if env_mode == "prd": f"{env_path}/{env_mode}/app.{env_mode}.env" 
    elif env_mode == "qa": f"{env_path}/{env_mode}/app.{env_mode}.env"
    else: f"{env_path}/{env_mode}/app.{env_mode}.env"

    out_path = f"{env_path}/{env_mode}/docker-compose.yml"
   
    #기존 파일 삭제 추가
    if os.path.exists(out_path):
        try:
             os.remove(out_path)
             print(f"[삭제] 기존 파일 제거: {out_path}")
        except Exception as e:
            print(f"[경고] 기존 파일 삭제 실패: {e}", file=sys.stderr)

    override_env_in_compose(f"{env_path}/base/docker-compose.base.yml", env_file,out_path)

