# TenderRadarLite

## 椤圭洰绠€浠?
TenderRadarLite 鏄竴涓潰鍚戝浗鍐呭叕寮€鎷涙姇鏍囩綉绔欑殑杞婚噺绾跨储鐩戞帶宸ュ叿銆?
褰撳墠鐗堟湰鑱氱劍锛?
- 鍏紑鎺ュ彛鎴栧叕寮€ HTML 鎶撳彇
- 鍏憡鍒楄〃鎵弿
- 璇︽儏瑙ｆ瀽
- 鍏憡绾?notice 鍘婚噸
- 鏈湴 SQLite 钀藉簱
- 瑙勫垯鍒嗙被
- 鍙€夐涔﹀缁磋〃鏍煎啓鍏?- 鍙€夐涔︾兢娑堟伅鎻愰啋
- Windows 鏈湴杩愯涓庢棩蹇楃暀瀛?
褰撳墠闃舵鏄彲寮€婧愬噯澶囩増锛屼笉浠ｈ〃鍏ㄥ浗瑕嗙洊锛屼篃涓嶅寘鍚噸鍨嬪悗鍙般€?
## 褰撳墠鑳藉姏

- 鍏紑鎺ュ彛鎶撳彇
- 鍓?3 椤垫壂鎻?- 璇︽儏瑙ｆ瀽
- 鍏憡绾?notice 鍘婚噸
- SQLite
- DIRECT / WATCHLIST / EXCLUDE 瑙勫垯鍒嗙被
- 鍙€夐涔﹀缁磋〃鏍?- 鍙€夌兢娑堟伅鎻愰啋
- Windows bat
- 鏃ュ織
- 鐧藉悕鍗?dry-run 涓庡彈鎺ч獙鏀?- 閿欒閫€鍑虹爜
- 鍥藉唴绔欑偣榛樿鐩磋繛锛屼笉渚濊禆绯荤粺浠ｇ悊

## 褰撳墠鏀寔鏉ユ簮

- 琛￠槼鍒嗗钩鍙板缓璁惧伐绋嬩氦鏄擄細宸查獙璇?- 琛￠槼鍒嗗钩鍙版斂搴滈噰璐氦鏄擄細淇濈暀 adapter锛屼絾榛樿 `disabled`锛屽綋鍓嶄笉鍙潬

褰撳墠鍙槸绗竴涓凡楠岃瘉鏉ユ簮绀轰緥锛屼笉浠ｈ〃鍏ㄥ浗瑕嗙洊銆?
## Windows 蹇€熷紑濮?
1. 瀹夎 Python 3.11 鎴栨洿楂樼増鏈€?2. 鍦ㄩ」鐩牴鐩綍鍒涘缓铏氭嫙鐜锛?
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. 瀹夎渚濊禆锛?
```powershell
python -m pip install -r requirements.txt
```

4. 澶嶅埗閰嶇疆妯℃澘锛?
```powershell
Copy-Item .env.example .env
```

5. 濡傞渶椋炰功杈撳嚭锛屽啀鎸夐渶濉啓 `.env` 涓殑椋炰功閰嶇疆锛涗笉浣跨敤椋炰功鍙暀绌恒€?6. 鍑嗗鐧藉悕鍗曠ず渚嬫枃浠讹紙鍙€夛級锛?
```powershell
Copy-Item examples\pilot_notice_ids.example.json examples\pilot_notice_ids.local.json
```

7. 鏈湴 dry-run锛?
```powershell
python run_mvp.py --local-only
```

8. 姝ｅ紡鍏ュ彛锛?
```powershell
python run_mvp.py
```

9. 鐧藉悕鍗曢獙鏀讹細

```powershell
python run_mvp.py --pilot-notice-ids-file examples\pilot_notice_ids.local.json --dry-run
python run_mvp.py --pilot-notice-ids-file examples\pilot_notice_ids.local.json --execute
```

10. 鏌ヨ搴旂敤鏈哄櫒浜哄彲瑙佺兢鑱婏細

```powershell
python run_mvp.py --list-feishu-chats
```

11. 娴嬭瘯椋炰功鏈哄櫒浜哄彂缇ゆ秷鎭細

```powershell
python run_mvp.py --test-feishu-bot
```

12. Windows bat锛?
```powershell
scripts\run_tender_radar.bat
```

13. 鏌ョ湅鏃ュ織锛?
- 杩愯鏃ュ織浣嶄簬 `logs\`
- 鏈湴鏁版嵁搴撲綅浜?`data\bids.db`

## 閰嶇疆璇存槑

- `config\sources.json`
  - 绠＄悊鏉ユ簮鍒楄〃銆佹ā鍧楄矾寰勩€佸惎鐢ㄧ姸鎬併€佸垎椤靛弬鏁?- `.env`
  - 椋炰功杈撳嚭鐩稿叧閰嶇疆
  - 鏈厤缃涔︽椂锛屾湰鍦版姄鍙栥€丼QLite銆佹棩蹇椾粛鍙繍琛?  - `FEISHU_BOT_MODE=webhook` 浣跨敤 `FEISHU_WEBHOOK_URL`
  - `FEISHU_BOT_MODE=app` 浣跨敤 `FEISHU_APP_ID`銆乣FEISHU_APP_SECRET`銆乣FEISHU_CHAT_ID`
  - 鍙厛鎵ц `python run_mvp.py --list-feishu-chats` 鑾峰彇 `chat_id`
- `examples\pilot_notice_ids.example.json`
  - 鐧藉悕鍗曞彈鎺ч獙鏀剁ず渚嬶紝闇€瑕佽嚜琛屽鍒跺悗濉啓
- AI API 褰撳墠灏氭湭鍚敤

## Feishu Bot Mode

- 褰撳墠鏀寔涓ょ涓诲姩鍙戠兢娑堟伅妯″紡锛歐ebhook 鍜?App Bot
- 褰撳墠 App Bot 妯″紡鍙仛搴旂敤鏈哄櫒浜轰富鍔ㄥ彂鏂囨湰娑堟伅
- 褰撳墠涓诲姩鍙戠兢娑堟伅涓嶉渶瑕侀暱杩炴帴
- 褰撳墠涓诲姩鍙戠兢娑堟伅涓嶉渶瑕佷簨浠惰闃?- 鍙湁鍦ㄥ悗缁鎺ユ敹鐢ㄦ埛娑堟伅銆佸仛 AI 瀵硅瘽鎴栧鐞嗗洖璋冩椂锛屾墠闇€瑕佷簨浠惰闃呮垨闀胯繛鎺?
## 瀹夊叏璇存槑

- 涓嶈鎻愪氦 `.env`
- 涓嶈鎻愪氦鏁版嵁搴?- 涓嶈鎻愪氦鏃ュ織
- 涓嶈鎻愪氦鐪熷疄 Secret銆乀oken銆乄ebhook
- 涓嶈鍏紑鏈湴璺緞
- 鍏紑鍓嶅繀椤诲仛涓€娆¤劚鏁忓璁?
## 宸茬煡杈圭晫

- 鍏紑缃戠珯鍙兘鏀圭増
- adapter 闇€瑕佹寔缁淮鎶?- 瑙勫垯鍒嗙被涓嶈兘鏇夸唬浜哄伐鍒ゆ柇
- 闄勪欢鏆備笉涓嬭浇瑙ｆ瀽
- AI API 灏氭湭鎺ュ叆
- 褰撳墠涓嶅仛澶嶆潅鍚庡彴

## Roadmap

## Windows Local HTML

- Windows 蹇€熷紑濮嬫枃妗ｏ細`docs/WINDOWS_QUICKSTART.md`
- 鎺ㄨ崘鍏堣繍琛?`scripts\妫€鏌ヨ繍琛岀幆澧?bat`锛屽啀杩愯 `scripts\鍚姩鏈湴鎷涙姇鏍囨姤鍛?bat`
- 鏈湴 HTML 鎶ュ憡涓嶉渶瑕?Feishu App Secret銆乄ebhook 鎴?`chat_id`

- 鏇村鍥藉唴甯哥敤鏉ユ簮
- Windows 鍒濆鍖栬剼鏈?- optional AI analysis adapter
- 杞婚噺鏈湴 HTML 鐪嬫澘
- 閽夐拤鎴栧叾浠栬緭鍑洪€傞厤鍣?- 鏇村畬鏁寸殑鏉ユ簮鍋ュ悍妫€鏌?