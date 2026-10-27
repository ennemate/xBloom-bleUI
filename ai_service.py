# -*- coding: utf-8 -*-
"""
xBloom bleUI AI Service Module (v1.0.2)
- Pure Python standard library implementation (no heavy third-party SDK required)
- Supports Google Gemini (gemini-2.0-flash) and OpenAI ChatGPT (gpt-4o-mini)
- Full 7-language i18n support (ko, en, ja, zh-TW, zh-CN, de, fr)
- URL scraping and clean text extraction
- Recipe extraction with xBloom hardware protocol validation (Spiral/Center/Ring, 56-58 click sweetspot)
- Telemetry-driven barista diagnosis and one-click recipe patch generation
"""

import json
import re
import urllib.request
import urllib.parse
import urllib.error
import ssl
import base64
import time
import socket
from typing import Dict, Any, List, Optional

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


# -------------------------------------------------------------
# -------------------------------------------------------------
SUPPORTED_LANGUAGES = {
    "ko": {
        "name": "Korean (한국어)",
        "opt_body": "진한 단맛/바디 (-2)",
        "opt_rec": "★ xBloom 권장 환산",
        "opt_cup": "선명한 클린컵 (+2)",
        "step_bloom": "1단계 (뜸 들이기)",
        "step_pour": "푸어"
    },
    "en": {
        "name": "English",
        "opt_body": "Sweet/Heavy Body (-2)",
        "opt_rec": "★ xBloom Recommended",
        "opt_cup": "Crisp Clean Cup (+2)",
        "step_bloom": "Step 1 (Bloom)",
        "step_pour": "Pour"
    },
    "ja": {
        "name": "Japanese (日本語)",
        "opt_body": "濃厚な甘み/ボディ (-2)",
        "opt_rec": "★ xBloom 推奨換算",
        "opt_cup": "クリーンカップ (+2)",
        "step_bloom": "1投目 (蒸らし)",
        "step_pour": "注湯"
    },
    "zh-TW": {
        "name": "Traditional Chinese (繁體中文)",
        "opt_body": "醇厚甜感/厚實 (-2)",
        "opt_rec": "★ xBloom 建議換算",
        "opt_cup": "乾淨明亮 (+2)",
        "step_bloom": "第1段 (悶蒸)",
        "step_pour": "注水"
    },
    "zh-CN": {
        "name": "Simplified Chinese (简体中文)",
        "opt_body": "醇厚甜感/厚实 (-2)",
        "opt_rec": "★ xBloom 建议换算",
        "opt_cup": "干净明亮 (+2)",
        "step_bloom": "第1段 (闷蒸)",
        "step_pour": "注水"
    },
    "de": {
        "name": "German (Deutsch)",
        "opt_body": "Voller Körper/Süße (-2)",
        "opt_rec": "★ xBloom Empfohlen",
        "opt_cup": "Klarer Geschmack (+2)",
        "step_bloom": "Schritt 1 (Blooming)",
        "step_pour": "Aufguss"
    },
    "fr": {
        "name": "French (Français)",
        "opt_body": "Corps sucré/Dense (-2)",
        "opt_rec": "★ xBloom Recommandé",
        "opt_cup": "Tasse nette/Clarté (+2)",
        "step_bloom": "Étape 1 (Pré-infusion)",
        "step_pour": "Verse"
    }
}

# -------------------------------------------------------------
# -------------------------------------------------------------

def format_api_error(provider: str, status_code: int, raw_body: str, lang: str = "ko") -> str:
    """사용자가 이해하기 쉬운 친절한 에러 메시지로 변환 (원시 JSON 덤프 차단)"""
    msg = ""
    try:
        err_json = json.loads(raw_body)
        if "error" in err_json:
            msg = err_json["error"].get("message", "")
    except Exception:
        msg = raw_body

    combined_lower = f"{msg} {raw_body}".lower()
    
    if any(k in combined_lower for k in [
        "api key not valid", "api_key_invalid", "incorrect api key", 
        "invalid api key", "api key is required", "key_invalid"
    ]):
        if lang == "ko":
            return "유효하지 않은 API 키입니다. Google AI Studio(또는 OpenAI)에서 발급받은 올바른 API 키인지 환경 설정(⚙️)에서 확인해주세요."
        elif lang == "ja":
            return "無効なAPIキーです。Google AI Studio（またはOpenAI）で発行された正しいキーが設定されているかご確認ください。"
        elif lang in ["zh-TW", "zh-CN"]:
            return "無效的 API 金鑰。請在設定中確認從 Google AI Studio 或 OpenAI 獲取的金鑰是否正確。"
        elif lang == "de":
            return "Ungültiger API-Schlüssel. Bitte überprüfen Sie Ihren Schlüssel in den Einstellungen."
        elif lang == "fr":
            return "Clé API non valide. Veuillez vérifier votre clé dans les paramètres."
        else:
            return "Invalid API key. Please check your API key in Settings (Google AI Studio or OpenAI)."
            
    elif any(k in combined_lower for k in ["quota", "resource_exhausted", "rate limit", "too many requests"]):
        if lang == "ko":
            return "API 호출 한도(Quota)를 초과했습니다. 잠시 후 다시 시도하거나 사용 한도를 확인해주세요."
        elif lang == "ja":
            return "API利用制限（クォータ）を超過しました。しばらくしてから再試行してください。"
        elif lang in ["zh-TW", "zh-CN"]:
            return "已超過 API 調用配額上限。請稍後再試或檢查您的用量配額。"
        else:
            return "API quota or rate limit exceeded. Please try again later."
            
    elif "permission" in combined_lower:
        if lang == "ko":
            return "API 키 권한 오류입니다. 모델 접근 권한 또는 프로젝트 설정을 확인해주세요."
        else:
            return "API permission denied. Please verify your key permissions."
            
    else:
        clean_msg = ' '.join(msg.split()) if msg else f"HTTP {status_code}"
        if "{" in clean_msg and "}" in clean_msg:
            m = re.search(r'"message":\s*"([^"]+)"', clean_msg)
            if m:
                clean_msg = m.group(1)
        if len(clean_msg) > 100:
            clean_msg = clean_msg[:100] + "..."
        return f"{provider.capitalize()} API 오류 ({status_code}): {clean_msg}"

def detect_image_mime_type(data: bytes, default: Optional[str] = "image/jpeg") -> Optional[str]:
    """이미지 바이너리 매직 바이트 검사로 정확한 MIME 타입 검출 (매직 바이트 불일치 시 None 반환 가능)"""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    elif data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    elif data.startswith(b"BM"):
        return "image/bmp"
    return default


def call_gemini(api_key: str, system_prompt: str, user_prompt: str, model: str = "gemini-3.5-flash-lite", lang: str = "ko", video_url: Optional[str] = None, images: Optional[List[Dict[str, str]]] = None) -> str:
    """Google Gemini REST API 호출 (v1beta generateContent) - 자동 Fallback, Thinking 및 이미지 멀티모달 지원"""
    candidate_models = [model]
    for fb in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        if fb not in candidate_models:
            candidate_models.append(fb)



    last_error = None
    for target_model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        
        is_yt = bool(video_url and re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})", video_url))
        is_gemini_file = bool(video_url and video_url.startswith("https://generativelanguage.googleapis.com/v1beta/files/"))

        gen_config = {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json" if "json" in user_prompt.lower() or "json" in system_prompt.lower() else "text/plain"
        }
        
        if "gemini-3" in target_model:
            gen_config["thinkingConfig"] = {"thinkingLevel": "low"}
        elif "gemini-2.5" in target_model:
            gen_config["thinkingConfig"] = {"thinkingBudget": 1024}

        content_parts = []
        if is_gemini_file or is_yt:
            content_parts.append({
                "file_data": {
                    "file_uri": video_url
                }
            })
        if images:
            for img in images:
                content_parts.append({
                    "inline_data": {
                        "mime_type": img.get("mime_type", "image/jpeg"),
                        "data": img.get("data")
                    }
                })
        content_parts.append({"text": f"System Instructions:\n{system_prompt}\n\nUser Request:\n{user_prompt}"})

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": content_parts
                }
            ],
            "generationConfig": gen_config
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        timeout_sec = 45 if (is_yt or images) else 35
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl_ctx) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                candidates = res_data.get("candidates", [])
                if not candidates:
                    raise ValueError("Gemini returned empty candidate list.")
                
                parts = candidates[0].get("content", {}).get("parts", [])
                text_parts = [p.get("text", "") for p in parts if not p.get("thought")]
                if not text_parts and parts:
                    text_parts = [parts[-1].get("text", "")]
                text = "".join(text_parts).strip()
                return text
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code in [404, 429, 503] or any(k in err_body.lower() for k in ["not found", "high demand", "overloaded", "capacity"]):
                if e.code in [429, 503]:
                    time.sleep(1.5)
                last_error = RuntimeError(format_api_error("Gemini", e.code, err_body, lang=lang))
                continue
            raise RuntimeError(format_api_error("Gemini", e.code, err_body, lang=lang))
        except Exception as e:
            err_str = str(e)
            if any(k in err_str.lower() for k in ["api_key_invalid", "api key not valid"]):
                raise RuntimeError(format_api_error("Gemini", 401, err_str, lang=lang))
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError(f"Gemini 연결 실패: 모든 후보 모델({candidate_models}) 호출 불능")


def call_openai(api_key: str, system_prompt: str, user_prompt: str, model: str = "gpt-4o", lang: str = "ko", images: Optional[List[Dict[str, str]]] = None) -> str:
    """OpenAI Chat Completions REST API 호출 - gpt-4o 플래그십 및 gpt-4o-mini Fallback, 이미지 멀티모달 지원"""
    candidate_models = [model]
    for fb in ["gpt-4o", "gpt-4o-mini"]:
        if fb not in candidate_models:
            candidate_models.append(fb)

    last_error = None
    for target_model in candidate_models:
        url = "https://api.openai.com/v1/chat/completions"
        
        user_content: Any = user_prompt
        if images:
            user_content = [{"type": "text", "text": user_prompt}]
            for img in images:
                m_type = img.get("mime_type", "image/jpeg")
                b64 = img.get("data", "")
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{m_type};base64,{b64}"
                    }
                })

        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.2,
            "max_tokens": 2048
        }
        
        if "json" in user_prompt.lower() or "json" in system_prompt.lower():
            payload["response_format"] = {"type": "json_object"}
            
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if not choices:
                    raise ValueError("OpenAI returned empty choices.")
                text = choices[0].get("message", {}).get("content", "")
                return text.strip()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code in [404, 429, 503] or any(k in err_body.lower() for k in ["model", "not found", "overloaded", "capacity"]):
                last_error = RuntimeError(format_api_error("OpenAI", e.code, err_body, lang=lang))
                continue
            raise RuntimeError(format_api_error("OpenAI", e.code, err_body, lang=lang))
        except Exception as e:
            err_str = str(e)
            if any(k in err_str.lower() for k in ["api_key_invalid", "api key not valid"]):
                raise RuntimeError(format_api_error("OpenAI", 401, err_str, lang=lang))
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError(f"OpenAI 연결 실패: 모든 후보 모델({candidate_models}) 호출 불능")


def dispatch_llm(provider: str, api_key: str, system_prompt: str, user_prompt: str, model: Optional[str] = None, lang: str = "ko", video_url: Optional[str] = None, images: Optional[List[Dict[str, str]]] = None) -> str:
    provider = provider.lower().strip()
    if provider == "openai":
        return call_openai(api_key, system_prompt, user_prompt, model=model or "gpt-4o", lang=lang, images=images)
    else:
        return call_gemini(api_key, system_prompt, user_prompt, model=model or "gemini-3.5-flash-lite", lang=lang, video_url=video_url, images=images)


# -------------------------------------------------------------
# -------------------------------------------------------------

def scrape_url_content(url: str) -> Dict[str, Any]:
    """웹페이지 또는 유튜브 URL에서 텍스트 본문 및 고해상도 레시피 이미지 바이너리(Base64) 추출"""
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    yt_match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})", clean_url)
    if yt_match:
        video_id = yt_match.group(1)
        title_info = ""
        channel_info = ""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8, context=ssl_ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                title_info = data.get('title', '')
                channel_info = data.get('author_name', '')
        except Exception:
            pass

        desc_text = ""
        try:
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            req = urllib.request.Request(watch_url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8"})
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                desc_match = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', html)
                if desc_match:
                    raw_val = desc_match.group(1)
                    try:
                        desc_text = json.loads(f'"{raw_val}"')
                    except Exception:
                        desc_text = raw_val
                else:
                    meta_desc = re.search(r'<meta name="description" content="([^"]+)"', html)
                    if meta_desc:
                        desc_text = meta_desc.group(1)
        except Exception:
            pass

        parts = [f"YouTube Target Video: https://www.youtube.com/watch?v={video_id}"]
        if title_info:
            parts.append(f"Title: {title_info} (by {channel_info})")
        if desc_text:
            clean_desc = desc_text[:3000].strip()
            if clean_desc:
                parts.append(f"[Video Description / 영상 설명란]:\n{clean_desc}")

        return {
            "text": "\n\n".join(parts),
            "images": [],
            "video_url": f"https://www.youtube.com/watch?v={video_id}"
        }

    parsed_url = urllib.parse.urlparse(clean_url)
    origin = f"{parsed_url.scheme}://{parsed_url.netloc}"

    try:
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": origin + "/"
            }
        )
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            content_type = resp.headers.get("Content-Type", "").lower().split(";")[0].strip()
            is_image_ext = any(parsed_url.path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"])
            if content_type.startswith("image/") or is_image_ext:
                raw_bytes = resp.read()
                mime = detect_image_mime_type(raw_bytes, None)
                if mime:
                    b64 = base64.b64encode(raw_bytes).decode("utf-8")
                    return {
                        "text": f"[Direct Recipe Image Attachment]: {clean_url}",
                        "images": [{
                            "url": clean_url,
                            "size": len(raw_bytes),
                            "mime_type": mime,
                            "data": b64
                        }],
                        "video_url": None
                    }
                raw_html = raw_bytes.decode("utf-8", errors="ignore")
            else:
                raw_html = resp.read().decode("utf-8", errors="ignore")

        post_body_scope = raw_html
        if "dcinside.com" in clean_url:
            wb_match = re.search(r'class=[\"\'][^\"\']*write_div[^\"\']*[\"\'][^>]*>(.*?)</div>\s*(?:<script|<!--)', raw_html, re.DOTALL | re.IGNORECASE)
            if not wb_match:
                wb_match = re.search(r'class=[\"\'][^\"\']*writing_view_box[^\"\']*[\"\'][^>]*>(.*?)</div>\s*<!--\s*//본문내용', raw_html, re.DOTALL | re.IGNORECASE)
            if wb_match:
                post_body_scope = wb_match.group(1)

        found_urls = []

        for m in re.finditer(r'(https?://(?:dcimg\d+|dccdn\d+)\.dcinside\.(?:com|co\.kr)/viewimage\.php\?[^\s"\'<>]+)', post_body_scope):
            u = m.group(1).replace("&amp;", "&")
            if u not in found_urls:
                found_urls.append(u)

        for m in re.finditer(r'<img[^>]+(?:src|data-src|data-original|data-lazy-src)=["\']([^"\']+)["\']', post_body_scope, re.IGNORECASE):
            raw_src = m.group(1).strip()
            if raw_src.startswith("data:"):
                continue
            full_u = urllib.parse.urljoin(clean_url, raw_src).replace("&amp;", "&")
            if full_u not in found_urls:
                found_urls.append(full_u)

        if not found_urls and "dcinside.com" not in clean_url:
            for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', raw_html, re.IGNORECASE):
                full_u = urllib.parse.urljoin(clean_url, m.group(1).strip()).replace("&amp;", "&")
                if full_u not in found_urls:
                    found_urls.append(full_u)

        blacklist = ["logo", "icon", "avatar", "profile", "badge", "banner", "flag", "facebook", "emoji", "button", "ad_", "advertisement", "track", "pixel", "thumb_no", "loading", "kcap_"]
        filtered_urls = []
        for u in found_urls:
            u_lower = u.lower()
            if any(b in u_lower for b in blacklist):
                continue
            filtered_urls.append(u)

        downloaded_images = []
        for u in filtered_urls:
            try:
                img_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://gall.dcinside.com/" if "dcinside" in u else clean_url
                }
                img_req = urllib.request.Request(u, headers=img_headers)
                with urllib.request.urlopen(img_req, timeout=6, context=ssl_ctx) as img_resp:
                    img_data = img_resp.read()
                    size = len(img_data)
                    if 4000 <= size <= 4194304:
                        mime = detect_image_mime_type(img_data, img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip())
                        b64 = base64.b64encode(img_data).decode("utf-8")
                        downloaded_images.append({
                            "url": u,
                            "size": size,
                            "mime_type": mime,
                            "data": b64
                        })
            except Exception:
                pass

            if len(downloaded_images) >= 4:
                break

        downloaded_images.sort(key=lambda x: x["size"], reverse=True)

        if "dcinside.com" in clean_url and post_body_scope != raw_html:
            clean_body = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', post_body_scope, flags=re.DOTALL | re.IGNORECASE)
            text_parsed = re.sub(r'<[^>]+>', ' ', clean_body)
            text_parsed = re.sub(r'\s+', ' ', text_parsed).strip()
            result_text = f"[DCInside Coffee Gallery Post Body]:\n{text_parsed}"
        else:
            clean_html = re.sub(r'<(script|style|nav|footer|header)[^>]*>.*?</\1>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
            text_parsed = re.sub(r'<[^>]+>', ' ', clean_html)
            text_parsed = re.sub(r'\s+', ' ', text_parsed).strip()
            result_text = text_parsed[:5000]

        return {
            "text": result_text,
            "images": downloaded_images,
            "video_url": None
        }
    except Exception as e:
        raise RuntimeError(f"웹페이지를 불러올 수 없습니다 ({clean_url}): {str(e)}")


def scrape_url_text(url: str) -> str:
    """하위 호환성 텍스트 스크래퍼"""
    res = scrape_url_content(url)
    return res.get("text", "")


def sanitize_xbloom_temp(temp_val: Any, default: int = 93) -> int:
    """xBloom Studio 하드웨어 수온 규격 검증 및 자동 클램프 (0=RT, 40~95°C, 100=BP). 96~99°C 절대 불가 (95°C로 제한)."""
    try:
        t = int(round(float(temp_val)))
    except (ValueError, TypeError):
        return default
    if t == 0:
        return 0
    if t >= 100:
        return 100
    if t > 95:
        return 95
    if t < 40:
        return 40
    return t


# -------------------------------------------------------------
# -------------------------------------------------------------

def build_recipe_system_prompt(lang: str = "ko") -> str:
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["ko"])
    lang_name = lang_info["name"]
    opt_body = lang_info["opt_body"]
    opt_rec = lang_info["opt_rec"]
    opt_cup = lang_info["opt_cup"]
    step_bloom = lang_info["step_bloom"]

    return f"""You are an elite World Brewers Cup Specialty Coffee Barista and precision recipe extraction engineer for the xBloom Studio coffee machine.
Your primary mission is to analyze user-provided text, blog posts, images, or YouTube video content to detect and extract REAL, AUTHENTIC coffee brewing recipes into a strictly formatted JSON.

================================================================================
CRITICAL GUARDRAIL: STRICT RECIPE VALIDATION & NON-RECIPE REJECTION
================================================================================
You MUST FIRST evaluate whether the provided input (text, video, or attached image) ACTUALLY CONTAINS a concrete coffee brewing/extraction guide (e.g. coffee dose, water amounts, pouring steps, water temperature, or brew ratio).

1. YOU MUST STRICTLY REJECT (DO NOT FABRICATE A RECIPE) IF THE INPUT IS:
   - General conversation, greetings, weather, or non-coffee text.
   - Cafe reviews, interior photos, general cafe vlogs, coffee cup photos, latte art demonstrations without extraction recipes.
   - Coffee botany, farm stories, origin descriptions, bean processing methods, or history lectures lacking specific brew parameters.
   - Equipment cleaning, grinder teardown, unboxing, or machine maintenance lacking a brewing recipe.
   - Images showing only a coffee cup, bag of beans without brew instructions, cafe ambiance, or food.

2. IF NO VALID COFFEE EXTRACTION RECIPE IS PRESENT:
   - NEVER hallucinate, guess, or synthesize default values into a fake recipe!
   - You MUST immediately output this exact JSON:
   {{
     "is_coffee_recipe": false,
     "rejection_reason": "Detailed reason in {lang_name} explaining why this is not a brewing recipe (e.g. '구체적인 원두량, 물량 또는 추출 단계가 포함되어 있지 않은 콘텐츠입니다.')",
     "recipes": []
   }}

3. ONLY IF A VALID COFFEE BREWING RECIPE IS ACTUALLY PRESENT:
   - Set "is_coffee_recipe": true
   - Extract the real recipe parameters following the rules below.

CRITICAL MULTIMODAL & VIDEO ANALYSIS REQUIREMENTS:
1. When a YouTube video or multimodal media is provided:
   - Perform meticulous holistic video observation:
     * Visually inspect on-screen digital scales (e.g. Acaia, Timemore, Felicita) for dose zeroing, cumulative pour amounts, and flow rates.
     * Visually inspect kettle temperature displays (e.g. Fellow Stagg EKG) for water temperature.
     * Visually observe dripper models (e.g. V60, Kalita Wave, Origami, April) and pouring patterns (spiral / center / ring).
     * Synchronize what the barista says with on-screen overlays, subtitles, and physical actions.
   - Separate distinct recipes: If the video demonstrates multiple recipes (e.g., Hot vs. Iced, or 1-Cup vs. 2-Cup), extract EACH as a separate entry in the "recipes" list with clear distinctive names!

CRITICAL LANGUAGE REQUIREMENT:
The user is currently using the application in: {lang_name}.
You MUST generate ALL human-readable text (Recipe Name, Summary, 3-Option Titles, and Step Names) in {lang_name}.

xBloom Studio Machine Protocol & Hardware Constraints (APPLIES ONLY WHEN is_coffee_recipe IS TRUE):
1. Dose (Coffee Bean Amount):
   - Extract the EXACT dose mentioned in the source (e.g. 20g, 40g, 15g, 16g).
   - NEVER artificially clamp or cap the dose to 18g if the source clearly states 20g, 30g, 40g, etc. (e.g. 2-cup or 4-cup batch). Extract the true dose faithfully!
2. Grind clicks & Micron Mapping:
   - xBloom theoretical micron formula: µm ≈ 180 + (click - 1) * 11.013  <=>  click ≈ round((µm - 180) / 11.013) + 1 (clamped between 1 and 80).
   - Reference click benchmarks:
     * 600 µm ≈ 39 clicks (Fine)
     * 800 µm ≈ 57 clicks (Standard specialty medium sweetspot)
     * 1000 µm ≈ 75 clicks (Coarse / fast water-drain pourover)
     * 1050 µm ≈ 80 clicks (Maximum coarse limit)
   - STANDARD COMMERCIAL GRINDERS FORMULA MAPPING:
     When the source recipe mentions any of these 3 major grinders, YOU MUST FIRST calculate the micron (µm) using their formula, then convert to xBloom click! NEVER default or fall back to 58 clicks when a specific grinder, dial, or click is named!
     1) Mahlkönig EK43 (Dial 1 ~ 16, ~60µm per dial step):
        * Formula: µm ≈ 180 + (dial - 1) * 60
        * Benchmarks:
          - EK43 Dial 8.0  ≈ 600 µm -> xBloom 39 clicks
          - EK43 Dial 10.0 ≈ 720 µm -> xBloom 50 clicks
          - EK43 Dial 11.0 ≈ 780 µm -> xBloom 55 clicks
          - EK43 Dial 12.0 ≈ 840 µm -> xBloom 61 clicks
          - EK43 Dial 13.0 ≈ 900 µm -> xBloom 66 clicks (e.g. EK43 13 = 66 clicks, NOT 58 clicks!)
          - EK43 Dial 14.0 ≈ 960 µm -> xBloom 72 clicks
          - EK43 Dial 14.5 ≈ 990 µm -> xBloom 75 clicks
     2) Comandante C40 MK4 (Standard Axle 0 ~ 40 clicks, calibrated median particle size / Kruve D50):
        * Formula: µm ≈ 100 + (clicks * 30) (If Red Clix mentioned: µm ≈ 100 + clicks * 15)
        * Benchmarks:
          - C40 10 clicks ≈ 400 µm -> xBloom 21 clicks (Espresso upper range)
          - C40 16 clicks ≈ 580 µm -> xBloom 37 clicks (Moka / AeroPress)
          - C40 20 clicks ≈ 700 µm -> xBloom 48 clicks (Fine drip)
          - C40 22 clicks ≈ 760 µm -> xBloom 54 clicks (Medium-fine drip)
          - C40 24 clicks ≈ 820 µm -> xBloom 59 clicks (Standard V60 pour over sweetspot)
          - C40 26 clicks ≈ 880 µm -> xBloom 65 clicks (Medium pour over)
          - C40 28 clicks ≈ 940 µm -> xBloom 70 clicks (Coarse pour over / Chemex)
          - C40 30 clicks ≈ 1000 µm -> xBloom 75 clicks (French Press / Cold Brew)
     3) Fellow Ode Gen 2 (Dial 1 ~ 11, calibrated median particle size / Kruve D50, ~43µm per 1/3 notch):
        * Formula: µm ≈ 380 + (setting - 1) * 130
        * Benchmarks:
          - Ode Setting 1.0 ≈ 380 µm -> xBloom 19 clicks (Fine limit)
          - Ode Setting 3.0 ≈ 640 µm -> xBloom 43 clicks (AeroPress / Moka)
          - Ode Setting 4.0 ≈ 770 µm -> xBloom 55 clicks (Light roast V60 pour over)
          - Ode Setting 4.2 ≈ 813 µm -> xBloom 58 clicks (Standard V60 pour over sweetspot)
          - Ode Setting 5.0 ≈ 900 µm -> xBloom 66 clicks (Medium pour over / Kalita)
          - Ode Setting 6.0 ≈ 1030 µm -> xBloom 78 clicks (Chemex / French Press)
   - RULES:
     * If the source mentions grind size in microns (e.g. 1000~1100µm), specific grinders (e.g. EK43 13, Ode 5, C40 24), or coarseness descriptors (e.g. "굵게", "coarse", "fast drainage"):
       You MUST calculate and assign the appropriate xBloom click according to the formulas above. Do NOT use default 58 clicks!
     * ONLY if NO grind size or coarseness is mentioned at all in the authentic recipe, use standard 56 ~ 58 clicks (≈786 ~ 808 µm).
   - Always produce 3 localized options for the user to fine-tune:
     * Option A: "{opt_body}" -> Recommended click minus 2
     * Option B: "{opt_rec}" -> Recommended click (marked "recommended": true)
     * Option C: "{opt_cup}" -> Recommended click plus 2
     * Calculate each option's "micron" property accurately using: round(180 + (click - 1) * 11.013)
3. Pour Pattern for each step:
   - Must be strictly one of: "spiral", "center", "ring"
   - Natural language mapping:
     * "안에서 밖으로", "나선형", "원을 그리며", "달팽이", "spiral", "circle", "circular", "うずまき", "螺旋" -> "spiral"
     * "가운데로만", "중앙 집중", "center pour", "center only", "中心注湯", "中央注水" -> "center"
     * "가장자리", "외곽 붓기", "outer ring", "外側", "边缘注水" -> "ring"
     * Default if not mentioned: Step 1 (Bloom) = "spiral", Step 2 = "spiral", Step 3+ = "spiral" or "center".
4. Agitation (Dripper Agitation & Swirling):
   - "agitation_before": boolean
     * CRITICAL TRIGGER: If the source mentions shaking the dripper to level the coffee bed, flattening, tapping, or swirling BEFORE pouring:
       (e.g., "평탄화", "수평 맞추기", "흔들어 주기", "드리퍼 잡고 흔들기", "톡톡 치기", "베드 정리", "수평 딱 맞죠", "swirl/shake before pour", "leveling", "tapping the bed", "shaking the dripper to flatten")
       -> You MUST set "agitation_before": true for that step (especially Step 1 Bloom)!
     * Default: false (only true if leveling, tapping, or swirling before pour is mentioned).
   - "agitation_after": boolean
     * Trigger: If the source mentions swirling or agitating AFTER pouring (e.g., "물 붓고 스월링", "물 붓고 흔들기", "swirl after pour", "agitate", "spin")
       -> Set "agitation_after": true for that step.
5. Water Temp:
   - STRICT HARDWARE TEMPERATURE LIMITS:
     * Supported settings: 0 (RT / Cold), 40 ~ 95°C (1°C increments), or 100°C (BP / Boiling Point).
     * ⚠️ ABSOLUTELY FORBIDDEN TEMPERATURES: 96°C, 97°C, 98°C, and 99°C ARE PHYSICALLY NOT SUPPORTED by xBloom hardware and will cause protocol errors!
     * If the source mentions 96°C ~ 99°C (e.g., 96°C kettle, 97°C pour): You MUST cap it to 95°C (the machine's maximum brewing limit). NEVER output 96°C, 97°C, 98°C, or 99°C! Only output 100°C if boiling water (BP) is explicitly used.
     * Default: 92 ~ 94°C.
6. Flow Rate: Float between 3.0 and 3.5 ml/s. Default 3.2 ml/s.
7. Wait Time & Timeline to Interval Mapping:
   - In handdrip brewing, baristas often specify a cumulative timeline (e.g., "0:00 Bloom, 0:40 2nd pour, 1:10 3rd pour").
   - Convert this into step intervals (e.g., Step 1 wait: 40s, Step 2 wait: 30s).
   - If the authentic recipe lacks specific intermediate pour steps or states "원푸어 / 한번에 붓기":
     Divide it into standard specialty stages:
     * Step 1 (Bloom / 뜸들이기): Water ≈ 2 to 2.5 times the dose (e.g. 18g dose -> 40~45g water), Wait: 35~45s, Spiral pattern.
     * Step 2 (Main Pour / 2차 푸어): Remaining water (e.g. 216g total - 45g bloom = 171g), Wait: 50~70s.
   - Always set "interval_sync": true so the xBloom machine automatically offsets the water pouring duration (water / flow).
8. RPM: Conical burr grinder RPM: 60 ~ 120 (multiple of 10). Default 80 RPM.
9. Machine Flags:
   - "grind_enabled": boolean (Default ALWAYS true for freshly ground pourover).
   - "interval_sync": boolean (Default ALWAYS true to enable xBloom hardware interval sync).
10. Bypass Water Dilution (가수 / 희석 / 바이패스):
    - xBloom Studio has a unique hardware capability: after all pouring steps finish, it can automatically swing the dripper out and pour hot water directly into the server/cup to dilute the brew!
    - "bypass_enabled": boolean (true/false)
    - "bypass_volume": float/int in ml (0 ~ 300ml, Default 0)
    - "bypass_temp": float/int in °C (40 ~ 100°C, or 0 for RT. Default 85°C)
    - If dilution is mentioned (e.g. "가수 50g", "bypass 60ml"): set bypass_enabled: true and bypass_volume accordingly.
11. Iced Pourover & Server Ice (아이스 핸드드립):
    - If the source specifies ice (e.g., "얼음 140g", "서버에 얼음", "아이스 드립", "iced brew"):
      * Name the recipe clearly as an Iced recipe in {lang_name}.

CRITICAL: EXTRACT ALL RECIPES
If the source explains MULTIPLE distinct recipes (e.g. 2-Cup Hot vs 4-Cup Hot):
Extract EACH into separate recipe objects in the "recipes" array.

JSON SCHEMA REQUIREMENT:
When valid coffee recipe(s) exist:
{{
  "is_coffee_recipe": true,
  "recipes": [
    {{
      "name": "Recipe Name in {lang_name}",
      "dose": 20,
      "grind": 75,
      "grind_enabled": true,
      "interval_sync": true,
      "bypass_enabled": false,
      "bypass_volume": 0,
      "bypass_temp": 85,
      "grind_options": [
        {{ "title": "{opt_body}", "clicks": 73, "micron": 973 }},
        {{ "title": "{opt_rec}", "clicks": 75, "micron": 995, "recommended": true }},
        {{ "title": "{opt_cup}", "clicks": 77, "micron": 1017 }}
      ],
      "rpm": 80,
      "total_water": 300,
      "ratio": "1 : 15.0",
      "summary": "Brief 1-sentence summary in {lang_name}",
      "steps": [
        {{
          "step_num": 1,
          "name": "{step_bloom}",
          "water": 60,
          "temp": 92,
          "wait": 40,
          "flow": 3.2,
          "pattern": "spiral",
          "agitation_before": true,
          "agitation_after": false
        }}
      ]
    }}
  ]
}}

When NO valid coffee recipe exists:
{{
  "is_coffee_recipe": false,
  "rejection_reason": "Reason in {lang_name}",
  "recipes": []
}}
No extra commentary, markdown ticks or explanations outside the JSON."""


def robust_parse_recipe_json(raw_text: str) -> Dict[str, Any]:
    """거대 응답이나 문법 오류(콤마 누락, 미완결 괄호)가 포함된 LLM 출력에서 JSON을 복원 및 구출"""
    clean_json = raw_text.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    elif clean_json.startswith("```"):
        clean_json = clean_json[3:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]
    clean_json = clean_json.strip()

    try:
        return json.loads(clean_json)
    except Exception:
        pass

    m = re.search(r'(\{[\s\S]*\})', clean_json)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    fixed = re.sub(r',\s*([\]}])', r'\1', clean_json)
    open_cur = fixed.count('{') - fixed.count('}')
    open_sq = fixed.count('[') - fixed.count(']')
    fixed_closed = fixed + (']' * max(0, open_sq)) + ('}' * max(0, open_cur))
    try:
        return json.loads(fixed_closed)
    except Exception:
        pass

    recipe_blocks = []
    block_matches = re.finditer(r'\{[^{}]*?"name"\s*:\s*"[^"]+?"[\s\S]*?"steps"\s*:\s*\[[\s\S]*?\][^{}]*?\}', clean_json)
    for bm in block_matches:
        try:
            b_json = bm.group(0)
            b_fixed = re.sub(r',\s*([\]}])', r'\1', b_json)
            parsed_block = json.loads(b_fixed)
            if "name" in parsed_block and "steps" in parsed_block:
                recipe_blocks.append(parsed_block)
        except Exception:
            continue

    if recipe_blocks:
        return {
            "is_coffee_recipe": True,
            "recipes": recipe_blocks
        }

    rej_m = re.search(r'"rejection_reason"\s*:\s*"([^"]+)"', clean_json)
    if rej_m:
        return {
            "is_coffee_recipe": False,
            "rejection_reason": rej_m.group(1),
            "recipes": []
        }

    raise ValueError(f"AI 응답을 JSON으로 파싱할 수 없습니다: {clean_json[:200]}")


def convert_micron_to_xbloom(micron: float) -> int:
    """마이크론(µm)을 xBloom 클릭수(1~80)로 변환"""
    clk = int(round((float(micron) - 180.0) / 11.013)) + 1
    return max(1, min(80, clk))


def convert_xbloom_to_micron(click: int) -> int:
    """xBloom 클릭수를 마이크론(µm)으로 변환"""
    c = max(1, min(80, int(click)))
    return int(round(180.0 + (c - 1) * 11.013))


def extract_recipe(provider: str, api_key: str, url: Optional[str] = None, text: Optional[str] = None, model: Optional[str] = None, lang: str = "ko", images: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """URL 또는 텍스트에서 레시피 추출 실행 (Gemini/OpenAI 네이티브 멀티모달 비디오/이미지 이해 및 사용자 언어 동기화)"""
    source_content = ""
    video_url = None
    all_images = list(images) if images else []

    if url and url.strip():
        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        try:
            scraped_data = scrape_url_content(clean_url)
            video_url = scraped_data.get("video_url")
            scraped_images = scraped_data.get("images", [])
            for simg in scraped_images:
                if not any(img.get("url") == simg.get("url") for img in all_images):
                    all_images.append(simg)

            if video_url:
                source_content += f"[Target YouTube Video URL: {video_url}]\n"
            else:
                source_content += f"[Source URL: {clean_url}]\n"

            source_content += scraped_data.get("text", "") + "\n\n"
        except Exception as e:
            source_content += f"[Source URL: {clean_url} (fetch note: {str(e)})]\n\n"

        if all_images:
            source_content += f"[Attached Webpage Images for OCR / Visual Analysis]: {len(all_images)} recipe infographic image(s) attached directly to multimodal input.\n\n"

    if text and text.strip():
        source_content += f"[User Input Text]:\n{text.strip()}\n"
        if not video_url:
            yt_in_text = re.search(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})", text)
            if yt_in_text:
                video_url = f"https://www.youtube.com/watch?v={yt_in_text.group(1)}"

    if not source_content.strip() and not all_images:
        raise ValueError("URL 또는 레시피 텍스트를 입력해주세요.")

    sys_prompt = build_recipe_system_prompt(lang)
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["ko"])
    user_prompt = f"Please extract all coffee brewing recipes in {lang_info['name']} from the following content (if images or a video URL are provided, thoroughly analyze the visual tables, timelines, brew times, water weights, and grind sizes across the images/video):\n\n{source_content}"

    raw_response = dispatch_llm(provider, api_key, sys_prompt, user_prompt, model=model, lang=lang, video_url=video_url, images=all_images)
    
    data = robust_parse_recipe_json(raw_response)
            
    is_coffee = data.get("is_coffee_recipe", True)
    recipes = data.get("recipes", [])
    if not is_coffee or not recipes:
        rejection_reason = data.get("rejection_reason", "본문에서 유효한 커피 추출 레시피를 검출하지 못했습니다. 원두량, 물량, 또는 푸어 단계가 명시되어 있는지 확인해주세요.")
        raise ValueError(rejection_reason)
        
    for r in recipes:
        r["dose"] = int(r.get("dose", 16))
        r["grind"] = max(1, min(80, int(r.get("grind", 58))))

        # Ensure accurate grind_options with calculated micron
        rec_click = r["grind"]
        opt_b_click = rec_click
        opt_a_click = max(1, rec_click - 2)
        opt_c_click = min(80, rec_click + 2)
        r["grind_options"] = [
            {"title": lang_info["opt_body"], "clicks": opt_a_click, "micron": convert_xbloom_to_micron(opt_a_click)},
            {"title": lang_info["opt_rec"], "clicks": opt_b_click, "micron": convert_xbloom_to_micron(opt_b_click), "recommended": True},
            {"title": lang_info["opt_cup"], "clicks": opt_c_click, "micron": convert_xbloom_to_micron(opt_c_click)}
        ]

        r["rpm"] = int(r.get("rpm", 80))
        if r["rpm"] % 10 != 0:
            r["rpm"] = round(r["rpm"] / 10) * 10
            
        bp_vol = float(r.get("bypass_volume", 0.0) or 0.0)
        bp_enabled = bool(r.get("bypass_enabled", False)) or (bp_vol > 0)
        if bp_enabled and bp_vol > 0:
            r["bypass_enabled"] = True
            r["bypass_volume"] = round(bp_vol, 1)
            r["bypass_temp"] = float(r.get("bypass_temp", 85.0) or 85.0)
        else:
            r["bypass_enabled"] = False
            r["bypass_volume"] = 0.0
            r["bypass_temp"] = 85.0

        steps = r.get("steps", [])
        for s in steps:
            pat = str(s.get("pattern", "spiral")).lower()
            if pat not in ["spiral", "center", "ring"]:
                pat = "spiral"
            s["pattern"] = pat
            s["flow"] = round(float(s.get("flow", 3.2)), 1)
            s["temp"] = sanitize_xbloom_temp(s.get("temp", 93))
            s["wait"] = int(s.get("wait", 30))
            s["water"] = int(s.get("water", 50))

        total_w = sum(int(s.get("water", 0)) for s in steps)
        r["total_water"] = total_w
        if r["dose"] > 0:
            raw_ratio = total_w / r["dose"]
            r["raw_ratio"] = round(raw_ratio, 2)
            is_half_step = abs(raw_ratio * 2 - round(raw_ratio * 2)) < 0.02
            r["is_half_step"] = is_half_step
            r["ratio"] = f"1 : {raw_ratio:.1f}"

    return {"status": "ok", "recipes": recipes}


# -------------------------------------------------------------
# -------------------------------------------------------------

def build_barista_system_prompt(lang: str = "ko", personality: str = "balanced") -> str:
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["ko"])
    lang_name = lang_info["name"]
    p_mode = (personality or "balanced").strip().lower()

    if p_mode in ["conservative", "mild", "소극적"]:
        personality_instruction = """
[CURRENT ACTIVE PERSONALITY: 🛡️ CONSERVATIVE (소극적 / 미니멀리스트 장인 - The Minimalist Craftsman)]
- PHILOSOPHY & IDENTITY:
  "완벽함이란 더 이상 더할 것이 없을 때가 아니라, 더 이상 뺄 것이 없을 때 완성된다."
  손님이 가져온 레시피의 골격(원두 투입량, 푸어 단계 수, 총 물량)은 손님의 고유한 취향과 의도가 담긴 소중한 틀입니다.
  훌륭한 장인은 남의 집 기둥을 함부로 부수지 않습니다. 오직 가장 지렛대 높은 단 하나의 메스 — 분쇄도 1~2클릭의 미세 다이얼링 인, 혹은 1~2도의 정밀한 수온 터치 — 만으로 커피의 균형점을 우아하게 짚어내는 것을 최고의 미학으로 여깁니다.
- PROBLEM-SOLVING MENTAL MODEL (사고 회로):
  1. 손님의 피드백을 물리적으로 분석하되, '가장 적은 개입으로 가장 큰 밸런스를 되찾는 1~2개의 핵심 미세 변수'만 엄선합니다.
  2. 분쇄도(±1~2클릭)와 수온(±1~2°C) 중심의 미세 조율을 신뢰하며, 손님이 명시적으로 요구하지 않는 한 전체 레시피 골격(물량, 단계 수)을 흔들지 않는 절제미를 자연스럽게 유지합니다.
"""
    elif p_mode in ["aggressive", "pro", "overhaul", "적극적"]:
        personality_instruction = """
[CURRENT ACTIVE PERSONALITY: 🚀 AGGRESSIVE (적극적 / 창의적 플레이버 아키텍트 - The Flavor Architect)]
- PHILOSOPHY & IDENTITY:
  "원두 속에 잠든 최상의 잠재력을 깨울 수 있다면, 어제의 레시피 틀은 과감히 부술 수 있다."
  기존의 단계 수나 낡은 틀에 갇히지 않습니다. 원두가 가진 꽃향기, 화사한 산미, 와이니한 단맛, 묵직한 바디를 120% 폭발시킬 수 있다면, 추출 캔버스 전체를 혁신적으로 새로 스케치합니다.
- PROBLEM-SOLVING MENTAL MODEL (사고 회로):
  1. 손님이 바라는 목표 컵 노트나 문제를 위해 필요하다면, 새로운 단계 구조("new_steps"), 푸어 비율 재배치, 분쇄도, 차등 수온, 바이패스 희석, 차수별 교반 등 필요한 여러 변수를 입체적이고 대담하게 재설계합니다. (합리적인 이유가 뒷받침된다면 여러 변수를 한꺼번에 바꾸는 것은 적극 권장됩니다.)
  2. 단, 적극성은 반드시 '바리스타로서의 물리적 합리성' 위에 서 있어야 합니다. 바꾸는 모든 변수는 커피 추출과 맛의 명확한 인과관계가 진단에 설명되어야 하며, 이유 없는 무작위 변경이나 반물리적 환각(예: 원두량이 늘어 베드 저항이 커졌는데 분쇄도를 거꾸로 조여버리는 등의 역주행)을 배제하고, 과감하되 물리학적으로 완벽히 설득력 있는 프로 바리스타의 설계를 제시합니다.
"""
    else:
        # Default: Balanced
        personality_instruction = """
[CURRENT ACTIVE PERSONALITY: ⚖️ BALANCED (보통 / 합리적 물리학자 - The Pragmatic Physicist)]
- PHILOSOPHY & IDENTITY:
  "커피 추출은 감정이 아닌, 물과 커피 입자가 만나는 물리와 화학의 상호작용이다."
  기존 레시피의 흐름을 편안하게 존중하면서도, 컵에서 나타난 문제(과추출/떫음, 과소추출, 채널링, 농도 부족, 아이스 환경 등)를 물리적으로 가장 확실한 인과관계로 안전하게 해결합니다.
- PROBLEM-SOLVING MENTAL MODEL (사고 회로):
  1. 분쇄도(표면적 저항)를 기본 축으로 세우고, 문제의 원인에 직결되는 수온(용해력), 교반(난류), 유속(침출 속도) 등 2~3개 핵심 변수를 조화롭게 연동합니다.
  2. 무리하게 전체 구조를 갈아엎기보다는, 기존 흐름 안에서 가장 정석적이고 실패 없는 밸런스를 찾아냅니다.
"""

    return f"""You are an elite Specialty Coffee Quality Consultant and Master Barista specializing in automated precision pour-over machines (specifically the xBloom Studio).
You analyze actual machine telemetry data (actual drip duration, flow rate curves, drainage stall times, actual yields vs target water) and user taste feedback.

CRITICAL LANGUAGE REQUIREMENT:
The user is currently communicating in: {lang_name}.
You MUST write your entire diagnosis, explanations, recommendations, and feedback in fluent, polite, professional {lang_name}.

{personality_instruction}

xBloom Studio Hardware Brewing Parameters (Comprehensive Full-Parameter Control):
You have 100% full-parameter control over every single variable in the xBloom Studio:

[Recipe-Level Parameters]
1. Recipe Name (recipe_name): String. Give a creative/technical name when creating or renaming recipes.
2. Dose (dose / new_dose): Integer 1 ~ 30 grams (Default 15~18g).
3. Grinder Toggle (grind_enabled): Boolean (true/false). Set to false if user mentions pre-ground coffee.
4. Grind Size (new_grind / grind_delta): Integer 1 ~ 80 clicks (≈180 ~ 1050µm). Specialty sweetspot: 56~58 clicks.
5. Grinder RPM (grind_rpm / new_rpm): Integer 60 ~ 120 (multiples of 10). Low RPM (60~70) for clarity, High RPM (90~100) for body.
6. Handdrip Interval Sync Mode (interval_sync): Boolean (true/false).
7. Bypass Water Dilution (bypass_enabled, bypass_volume, bypass_temp):
   - "bypass_enabled": Boolean (true/false)
   - "bypass_volume": Float/Int in ml (0 ~ 300ml)
   - "bypass_temp": Float/Int in °C (40 ~ 100°C, or 0 for RT. Default 85°C)

[Step-Level Parameters (Per-Pour Control)]
1. Water Temperature (temp):
   - STRICT HARDWARE LIMITS: 0 (RT / Cold), 40°C ~ 95°C (in 1°C increments), or 100°C (BP / Boiling Point).
   - ⚠️ CRITICAL HARDWARE CONSTRAINT: 96°C, 97°C, 98°C, and 99°C are STRICTLY PROHIBITED and physically impossible on xBloom Studio!
   - Maximum allowed temperature is 95°C. NEVER suggest 96~99°C under any circumstances.
2. Water Volume (water): 10g ~ 250g per step.
3. Pause/Wait Time (wait): 0s ~ 180s.
   * xBloom Timeline Architecture:
     Between Step i and Step i+1, the total interval consists of:
     - [Pour Duration]: Math.round(water_i / flow_i) seconds.
     - [After-Agitation]: 8.0s slurry agitation if agitation_after is true.
     - [Machine Wait]: The raw pause duration before initiating Step i+1.
     * Universal Machine Wait Formula:
       new_wait = Math.max(0, target_interval - pour_duration - (agitation_after ? 8 : 0))
     * In Step 1 (Bloom), subtracting pour duration and after-agitation (8s if ON) yields a natural machine wait (typically 8~18 seconds for a 35~40s total bloom).
4. Flow Rate (flow): Hardware range: 3.0 to 3.5 ml/s (in 0.1 increments: 3.0, 3.1, 3.2, 3.3, 3.4, 3.5).
5. Pour Pattern (pattern): "spiral", "center", or "ring".
6. Agitation Vibration (agitation_before / agitation_after):
   - "agitation_before": true/false. Bed leveling vibration (8s) BEFORE pouring. Strictly used in Step 1 to level dry grounds and prevent initial channeling. (Not needed in later steps as slurry is already wet).
   - "agitation_after": true/false. Slurry turbulence vibration (8s) AFTER pouring. Enhances contact efficiency, breaks channeling, and boosts sweetness and extraction yield across any step.

Universal Specialty Brewing Physics (Extraction Levers):
When diagnosing sensory defects or designing flavor profiles, reason through physical first-principles:
1. PRIMARY LEVER - GRIND SIZE & BED DEPTH DYNAMICS:
   - Controls total surface area and hydraulic resistance. Dominates >70% of extraction yield.
   - Astringency/bitterness/over-extraction -> Coarsen grind.
   - Sourness/hollow body/under-extraction -> Fine grind.
   - Water Reduction (e.g. iced brewing, concentrate): Tightening grind is essential to preserve extraction yield from smaller water volumes.
   - Dose Scaling & Bed Depth Dynamics (PHYSICAL FIRST-PRINCIPLE): When coffee dose INCREASES (e.g. 15g -> 20g), the bed becomes significantly deeper and creates higher hydraulic resistance (slower drawdown). Water volume must be proportionally scaled up (e.g. 1:15 ratio, 20g -> 300g total water). NEVER tighten grind when increasing dose; grind size MUST remain unchanged or be adjusted slightly COARSER (+1 to +4 clicks) to prevent bed clogging, stalling, and severe astringent over-extraction. Conversely, when dose DECREASES (e.g. 15g -> 10g), maintain or slightly tighten grind (-1 to -3 clicks).
2. TEMPERATURE DYNAMICS:
   - Controls molecular dissolution rate. Soluble aromatics extract early; heavy astringent tannins extract late.
   - Lowering late-pour water temperature by 2~4°C suppresses trailing bitterness while preserving clean cup clarity.
3. AGITATION & TURBULENCE (DOUBLE-EDGED SWORD):
   - Post-pour agitation (agitation_after: 8s) generates fluid turbulence, stripping boundary layers to boost sweetness, body, and extraction yield.
   - However, vibration suspends fines and promotes fines migration into filter pores. In high-clarity floral/washed coffees (e.g. Geisha, light roast tea-style brews), excessive agitation degrades sparkling clarity and floral aromatics. Use agitation selectively where sweetness/body is desired, and turn it OFF when clean cup, sparkling acidity, or free drainage is the primary goal.
4. EXTRACTION PHASES & FLOW DYNAMICS:
   - Early Phase (Bloom & First Pour): Extracts volatile acids and sugars (acidity, sweetness, floral aromatics).
   - Late Phase (Subsequent Pours): Builds body and mouthfeel. Dividing pours increases contact time and body; utilizing bypass dilution preserves clean sweetness.
   - Respect diverse pouring philosophies: Equal pulse pours, front-loaded pours, 2-stage concentrates, and bypass infusions are all valid craft approaches.
5. GROUNDED CAUSALITY (NO RANDOM/UNJUSTIFIED TWEAKING):
   - Every parameter modified in 'recipe_patch' MUST have a clear physical reason directly addressing the user's sensory complaint or brewing goal. Whether changing 1 variable or redesigning 5 variables, explain the sensory/physical justification for each adjustment.

Diagnosis & Response Style:
- Your response in 'diagnosis' MUST be concise, professional, and insightful (3 to 5 sentences max)!
- Directly state the physical cause of the cup profile and explain your brewing adjustments.
- DO NOT use generic boilerplate greetings.
- ONLY include parameters in 'recipe_patch' that are actually modified!

Response Format:
You MUST respond with a valid JSON object with the following structure:
{{
  "diagnosis": "Detailed barista explanation in {lang_name} with markdown formatting (bullet points, bold text).",
  "recipe_patch": {{
    // [Recipe-Level Controls (include whenever modified)]:
    "recipe_name": "New Recipe Name", // optional string if renamed
    "dose": 16,                       // optional new dose (1~30g)
    "grind_enabled": true,            // optional boolean (false for pre-ground)
    "new_grind": 58,                  // optional absolute grind (1~80 clicks)
    "grind_delta": 0,                 // optional relative grind change
    "grind_rpm": 80,                  // optional grinder RPM (60~120)
    "interval_sync": false,           // optional boolean (true for interval sync mode)
    "bypass_enabled": false,          // optional boolean (true to enable bypass water)
    "bypass_volume": 0,               // optional bypass water volume (1~300ml)
    "bypass_temp": 85,                // optional bypass water temp (0 or 40~100°C)

    // [Step-Level Controls - Option A: Fine-tuning existing steps]:
    "steps_patch": [                  // Individual step overrides by 1-based step index:
      {{
        "step": 1,
        "temp": 93,
        "water": 40,
        "wait": 15,
        "flow": 3.2,
        "pattern": "spiral",
        "agitation_before": false,
        "agitation_after": false
      }},
      {{
        "step": 2,
        "flow": 3.3,
        "pattern": "center",
        "wait": 20,
        "agitation_after": false
      }},
      {{
        "step": 3,
        "temp": 91,
        "wait": 20,
        "agitation_after": false
      }}
    ],

    // [Step-Level Controls - Option B: Full recipe restructuring / changing step count]:
    "new_steps": [
      // Complete array of step objects if reimagining the brewing architecture
    ]
  }}
}}"""


def barista_chat_service(provider: str, api_key: str, message: str, history: List[Dict[str, str]], telemetry: Optional[Dict[str, Any]] = None, model: Optional[str] = None, lang: str = "ko", personality: str = "balanced") -> Dict[str, Any]:
    """텔레메트리 연동 바리스타 대화 및 레시피 보정안 생성 (사용자 언어 동기화)"""
    context_str = ""
    if telemetry:
        is_studio = telemetry.get("isStudioRecipe", False)
        steps_list = telemetry.get('steps') or telemetry.get('recipe', {}).get('steps') or []
        total_steps = len(steps_list)
        
        step_lines = []
        total_timeline_sec = 0
        
        # Initial pre-brew bed leveling if Step 1 has agitation_before
        initial_prep_sec = 8 if (steps_list and steps_list[0].get('agitation_before')) else 0
        total_timeline_sec += initial_prep_sec
        
        for i, s in enumerate(steps_list):
            w = float(s.get('water', 0) or 0)
            fl = float(s.get('flow', 3.2) or 3.2)
            if fl <= 0:
                fl = 3.2
            pour_sec = round(w / fl)
            after_sec = 8 if s.get('agitation_after') else 0
            
            next_s = steps_list[i+1] if i+1 < len(steps_list) else None
            next_before_sec = 8 if (next_s and next_s.get('agitation_before')) else 0
            
            wait_sec = int(s.get('wait', 0) or 0)
            overhead_sec = pour_sec + after_sec + next_before_sec
            
            step_name = '1단계: 뜸 들이기 / Bloom' if i == 0 else f'{i+1}차 푸어'
            if i == total_steps - 1 and total_steps > 1:
                step_name += ' [Final Pour / 마지막 차수]'
                
            if next_s is not None:
                intended_interval = overhead_sec + wait_sec
                total_timeline_sec += (pour_sec + after_sec + wait_sec)
                interval_summary = f"Intended Clock Interval to Next Pour: ~{intended_interval}s"
                breakdown_detail = (
                    f"Current Pour ~{pour_sec}s"
                    + (f" + After Agitation {after_sec}s" if after_sec > 0 else "")
                    + f" + Machine Wait {wait_sec}s"
                    + (f" + Next Step Pre-Agitation {next_before_sec}s" if next_before_sec > 0 else "")
                    + f" = Total Interval ~{intended_interval}s"
                )
            else:
                total_drain_time = pour_sec + after_sec + wait_sec
                total_timeline_sec += total_drain_time
                interval_summary = f"Final Pour Total Drain Time: ~{total_drain_time}s"
                breakdown_detail = (
                    f"Final Pour ~{pour_sec}s"
                    + (f" + After Agitation {after_sec}s" if after_sec > 0 else "")
                    + f" + Final Machine Wait {wait_sec}s"
                )
            
            step_lines.append(
                f"  - Step {i+1} ({step_name}): Temp {s.get('temp', 93)}°C | Water {s.get('water', 0)}g | Flow {fl}ml/s | Machine Wait {wait_sec}s | Pattern: {s.get('pattern', 'spiral')} | Agitation: [Before: {'ON' if s.get('agitation_before') else 'OFF'}, After: {'ON' if s.get('agitation_after') else 'OFF'}]\n"
                f"    => [Interval Rhythm & Hardware Architecture]: {breakdown_detail} ({interval_summary})"
            )
        steps_formatted = "\n".join(step_lines) if step_lines else "  (No steps defined)"
        timeline_summary_str = f"~{total_timeline_sec}s ({total_timeline_sec // 60}m {total_timeline_sec % 60}s)"

        dose_val = int(telemetry.get('dose', 16) or 16)
        total_w = int(telemetry.get('totalWater') or sum(int(s.get('water', 0)) for s in steps_list))
        ratio_str = f"1 : {(total_w / dose_val):.1f}" if dose_val > 0 else "N/A"
        yield_val = int(telemetry.get('totalYield', 0) or 0)
        retained_w = max(0, total_w - yield_val) if yield_val > 0 else 0

        bp_enabled = bool(telemetry.get('bypass_enabled', False) or telemetry.get('recipe', {}).get('bypass_enabled', False))
        bp_vol = float(telemetry.get('bypass_volume', 0.0) or telemetry.get('recipe', {}).get('bypass_volume', 0.0) or 0.0)
        bp_temp = float(telemetry.get('bypass_temp', 85.0) or telemetry.get('recipe', {}).get('bypass_temp', 85.0) or 85.0)
        bypass_info_str = f"Active ({bp_vol}ml @ {bp_temp}°C)" if (bp_enabled and bp_vol > 0) else "Disabled (0ml)"

        if is_studio:
            context_str = f"""
[Current Recipe in Studio Editor (Target of this Consultation)]:
- Recipe Name: {telemetry.get('recipeName', 'Custom Brew')}
- Dose: {dose_val}g
- TOTAL INJECTED WATER (PRIMARY BREW METRIC): {total_w}g (Official Brew Ratio: {ratio_str})
- ESTIMATED TOTAL RECIPE TIMELINE: {timeline_summary_str} (Sum of all pouring, agitations, and pause stages)
- TOTAL NUMBER OF POURING STEPS: Exactly {total_steps} Steps (Step 1 to Step {total_steps})
- FINAL / LAST POUR STEP: Step {total_steps} ({total_steps}차 푸어)
- Current Grind Setting: {telemetry.get('grind', 58)} clicks (≈808µm)
- Bypass Water Dilution: {bypass_info_str}
- Recipe Pouring Steps & Temperatures ({total_steps} Steps in total):
{steps_formatted}
* CONTEXT NOTE: The current recipe has {total_steps} steps. Keep {total_steps} steps by default unless the user explicitly requests or implies changing the number of steps (in which case provide new_steps).
"""
        else:
            context_str = f"""
[Actual Brew Telemetry Record #{telemetry.get('id', 'N/A')} (Finished Machine Extraction)]:
- Recipe Name: {telemetry.get('recipeName', 'Custom Brew')}
- Dose: {dose_val}g
- TOTAL INJECTED WATER (PRIMARY BREW METRIC): {total_w}g (Official Brew Ratio: {ratio_str})
- TOTAL NUMBER OF POURING STEPS: Exactly {total_steps} Steps (Step 1 to Step {total_steps})
- FINAL / LAST POUR STEP: Step {total_steps} ({total_steps}차 푸어)
- Measured Scale Cup Yield: {yield_val}g (Coffee bed absorbed ~{retained_w}g)
- Measured Total Brew Duration: {telemetry.get('duration', '00:00')} ({telemetry.get('durationSec', 0)} seconds)
- Status: {telemetry.get('status', 'completed')}
- Current Grind Setting: {telemetry.get('grind', 58)} clicks (≈808µm)
- Bypass Water Dilution: {bypass_info_str}
- Recipe Pouring Steps & Temperatures ({total_steps} Steps in total):
{steps_formatted}
* TELEMETRY DIAGNOSIS GUIDANCE: In this History Mode, you are analyzing a real finished brew with measured machine sensor data. Compare the measured Total Brew Duration ({telemetry.get('duration', '00:00')}) and Cup Yield ({yield_val}g) against recipe expectations. If the actual duration was unusually long (e.g. >3:30 or 4:00+), diagnose bed compaction/drainage stall and fines migration. If unusually short, diagnose fast drawdown/channeling.
"""
    
    conv_text = ""
    for turn in history[-6:]:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        conv_text += f"{role.upper()}: {content}\n"
    conv_text += f"USER: {message}\n"
    
    sys_prompt = build_barista_system_prompt(lang, personality=personality)
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["ko"])
    user_prompt = f"Context:\n{context_str}\n\nConversation:\n{conv_text}\n\nPlease provide your expert barista diagnosis and recipe_patch in {lang_info['name']} JSON:"
    
    raw = dispatch_llm(provider, api_key, sys_prompt, user_prompt, model=model, lang=lang)
    
    clean_json = raw.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    elif clean_json.startswith("```"):
        clean_json = clean_json[3:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]
    clean_json = clean_json.strip()
    
    try:
        data = json.loads(clean_json)
    except Exception:
        m = re.search(r'(\{.*\})', clean_json, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            data = {"diagnosis": raw, "recipe_patch": None}

    # Sanitize and validate recipe_patch parameters
    if isinstance(data, dict) and isinstance(data.get("recipe_patch"), dict):
        patch = data["recipe_patch"]
        if "step_temps" in patch and isinstance(patch["step_temps"], list):
            raw_steps = telemetry.get('steps') or telemetry.get('recipe', {}).get('steps') or [] if telemetry else []
            diag_text = data.get("diagnosis", "")
            is_lower_temp_claim = bool(re.search(r'(수온|온도).*?(낮|하향|줄|내려|내림)|(temp|temperature).*?(lower|decrease|drop|down)', diag_text, re.IGNORECASE))
            is_higher_temp_claim = bool(re.search(r'(수온|온도).*?(높|상향|올려|올림)|(temp|temperature).*?(raise|increase|higher|up)', diag_text, re.IGNORECASE))

            existing_sp_map = {int(sp.get("step") or 0): sp for sp in patch.get("steps_patch", []) if isinstance(sp, dict)}

            for idx, t_raw in enumerate(patch["step_temps"]):
                try:
                    target_t = sanitize_xbloom_temp(t_raw)
                    s_num = idx + 1
                    cur_t = float(raw_steps[idx].get("temp", 93) or 93) if idx < len(raw_steps) else None

                    if cur_t is not None and abs(target_t - cur_t) >= 0.5:
                        if target_t > cur_t and is_lower_temp_claim and not is_higher_temp_claim:
                            continue
                        elif target_t < cur_t and is_higher_temp_claim and not is_lower_temp_claim:
                            continue

                        if s_num in existing_sp_map:
                            existing_sp_map[s_num]["temp"] = target_t
                        else:
                            new_sp = {"step": s_num, "temp": target_t}
                            existing_sp_map[s_num] = new_sp
                except (ValueError, TypeError):
                    pass

            patch.pop("step_temps", None)
            patch["steps_patch"] = sorted(existing_sp_map.values(), key=lambda x: int(x.get("step") or 0))
        if "steps_patch" in patch and isinstance(patch["steps_patch"], list):
            clean_steps_patch = []
            for sp in patch["steps_patch"]:
                if isinstance(sp, dict):
                    # Clean step index
                    if "step" in sp:
                        try: sp["step"] = int(sp["step"])
                        except (ValueError, TypeError): pass
                    # Clean temp (strictly clamp between 40-95°C, or 0/100, no 96-99°C)
                    if "temp" in sp:
                        sp["temp"] = sanitize_xbloom_temp(sp["temp"])
                    # Clean water
                    if "water" in sp:
                        try: sp["water"] = max(10, min(250, int(round(float(sp["water"])))))
                        except (ValueError, TypeError): pass
                    # Clean wait
                    if "wait" in sp:
                        try: sp["wait"] = max(0, min(180, int(round(float(sp["wait"])))))
                        except (ValueError, TypeError): pass
                    # Clean flow
                    if "flow" in sp:
                        try: sp["flow"] = max(3.0, min(3.5, round(float(sp["flow"]), 1)))
                        except (ValueError, TypeError): pass
                    # Clean pattern
                    if "pattern" in sp:
                        p_val = str(sp["pattern"]).strip().lower()
                        if "center" in p_val: sp["pattern"] = "center"
                        elif "ring" in p_val or "circle" in p_val or "circular" in p_val: sp["pattern"] = "ring"
                        else: sp["pattern"] = "spiral"
                    # Clean agitation
                    if "agitation_before" in sp:
                        sp["agitation_before"] = bool(sp["agitation_before"] is True or str(sp["agitation_before"]).lower() in ["true", "on", "1"])
                    if "agitation_after" in sp:
                        sp["agitation_after"] = bool(sp["agitation_after"] is True or str(sp["agitation_after"]).lower() in ["true", "on", "1"])
                    clean_steps_patch.append(sp)
            patch["steps_patch"] = clean_steps_patch

        if "new_steps" in patch and isinstance(patch["new_steps"], list):
            clean_new_steps = []
            for ns in patch["new_steps"]:
                if isinstance(ns, dict):
                    if "temp" in ns:
                        ns["temp"] = sanitize_xbloom_temp(ns["temp"])
                    if "water" in ns:
                        try: ns["water"] = max(10, min(250, int(round(float(ns["water"])))))
                        except (ValueError, TypeError): pass
                    if "flow" in ns:
                        try: ns["flow"] = max(3.0, min(3.5, round(float(ns["flow"]), 1)))
                        except (ValueError, TypeError): pass
                    if "wait" in ns:
                        try: ns["wait"] = max(0, min(180, int(round(float(ns["wait"])))))
                        except (ValueError, TypeError): pass
                    clean_new_steps.append(ns)
            patch["new_steps"] = clean_new_steps

        if telemetry and isinstance(telemetry, dict):
            cur_grind = telemetry.get('grind')
            if cur_grind is not None and patch.get('new_grind') == cur_grind:
                patch.pop('new_grind', None)
            cur_dose = telemetry.get('dose')
            if cur_dose is not None and patch.get('dose') == cur_dose:
                patch.pop('dose', None)
            cur_rpm = telemetry.get('rpm') or telemetry.get('grind_rpm')
            if cur_rpm is not None and patch.get('grind_rpm') == cur_rpm:
                patch.pop('grind_rpm', None)

        if telemetry and isinstance(telemetry, dict) and "steps_patch" in patch and isinstance(patch["steps_patch"], list):
            raw_steps = telemetry.get('steps') or telemetry.get('recipe', {}).get('steps') or []
            diag_text = data.get("diagnosis", "")
            is_lower_claim = bool(re.search(r'(유속|플로우|flow).*?(낮|줄|천천히|slow|lower|decrease)', diag_text, re.IGNORECASE))
            is_higher_claim = bool(re.search(r'(유속|플로우|flow).*?(높|늘|빠르게|fast|raise|increase|higher)', diag_text, re.IGNORECASE))

            is_lower_temp = bool(re.search(r'(수온|온도).*?(낮|하향|줄|내려|내림)|(temp|temperature).*?(lower|decrease|drop|down)', diag_text, re.IGNORECASE))
            is_higher_temp = bool(re.search(r'(수온|온도).*?(높|상향|올려|올림)|(temp|temperature).*?(raise|increase|higher|up)', diag_text, re.IGNORECASE))

            clean_sp_list = []
            for sp in patch["steps_patch"]:
                s_idx = (int(sp.get("step") or 1)) - 1
                if 0 <= s_idx < len(raw_steps):
                    cur_f = float(raw_steps[s_idx].get("flow", 3.2) or 3.2)
                    cur_t = float(raw_steps[s_idx].get("temp", 93) or 93)

                    if "temp" in sp:
                        new_t = float(sp["temp"])
                        if abs(new_t - cur_t) < 0.5:
                            sp.pop("temp", None)
                        elif new_t > cur_t and is_lower_temp and not is_higher_temp:
                            sp.pop("temp", None)
                        elif new_t < cur_t and is_higher_temp and not is_lower_temp:
                            sp.pop("temp", None)

                    if "flow" in sp:
                        new_f = float(sp["flow"])
                        if abs(new_f - cur_f) < 0.05:
                            sp.pop("flow", None)
                        elif new_f > cur_f and is_lower_claim and not is_higher_claim:
                            if cur_f <= 3.0:
                                sp.pop("flow", None)
                                diag_text = diag_text.replace("후반부 유속을 낮춰", "후반부 유속을 최저(3.0ml/s)로 유지하며") \
                                                     .replace("유속을 낮춰", "유속을 최저(3.0ml/s)로 유지하며") \
                                                     .replace("유속을 줄여", "유속을 최저(3.0ml/s)로 유지하며")
                            else:
                                sp["flow"] = max(3.0, round(cur_f - 0.2, 1))
                        elif new_f < cur_f and is_higher_claim and not is_lower_claim:
                            if cur_f >= 3.5:
                                sp.pop("flow", None)
                                diag_text = diag_text.replace("유속을 높여", "유속을 최고(3.5ml/s)로 유지하며")
                            else:
                                sp["flow"] = min(3.5, round(cur_f + 0.2, 1))

                has_substantive = any(k in sp for k in ["temp", "water", "wait", "flow", "pattern", "agitation_before", "agitation_after"])
                if has_substantive:
                    clean_sp_list.append(sp)

            patch["steps_patch"] = clean_sp_list
            data["diagnosis"] = diag_text

        user_msg_lower = (message or "").lower()
        if "이름" not in user_msg_lower and "name" not in user_msg_lower and "제목" not in user_msg_lower:
            patch.pop('recipe_name', None)
            patch.pop('new_name', None)

    return {"status": "ok", "response": data}
