import json
import requests
import time
from typing import List, Dict, Optional, Callable
import os
import sqlite3
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import hashlib
import traceback
import psutil
import threading
import signal
import atexit
import sys
import re
from collections import deque
from dataclasses import dataclass, field
from functools import wraps
from flask import Flask, request, jsonify, Response, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import zipfile
import uuid
from datetime import datetime as dt

# ============== VERBOSE DEBUG MODE ==============
VERBOSE_DEBUG = True  # Set to False to reduce console output
# ================================================

# ============== PATH CONFIGURATION ==============
# Detect if we're running as a packaged .exe
def get_app_paths():
    """Get the correct paths based on execution environment"""
    if getattr(sys, 'frozen', False):
        # Running as packaged .exe with PyInstaller
        # APP_DIR: where the .exe is located (for persistent data)
        # BUNDLE_DIR: where PyInstaller extracted files (for static/)
        app_dir = os.environ.get('BOOK_TRANSLATOR_APP_DIR', os.path.dirname(sys.executable))
        bundle_dir = os.environ.get('BOOK_TRANSLATOR_BUNDLE_DIR', getattr(sys, '_MEIPASS', app_dir))
    else:
        # Running as normal Python script
        app_dir = os.path.dirname(os.path.abspath(__file__))
        bundle_dir = app_dir
    return app_dir, bundle_dir

APP_DIR, BUNDLE_DIR = get_app_paths()
# ================================================

app = Flask(__name__, static_folder=os.path.join(BUNDLE_DIR, 'static'))
CORS(app)

# Folders setup - use APP_DIR for persistent data
UPLOAD_FOLDER = os.path.join(APP_DIR, 'uploads')
TRANSLATIONS_FOLDER = os.path.join(APP_DIR, 'translations')
STATIC_FOLDER = os.path.join(BUNDLE_DIR, 'static')
LOG_FOLDER = os.path.join(APP_DIR, 'logs')
DB_PATH = os.path.join(APP_DIR, 'translations.db')
CACHE_DB_PATH = os.path.join(APP_DIR, 'cache.db')

# Create necessary directories
for folder in [UPLOAD_FOLDER, TRANSLATIONS_FOLDER, LOG_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ============== IN-MEMORY LOG BUFFER ==============
# This buffer stores logs for the frontend console panel
class LogBuffer:
    """Thread-safe circular buffer for storing logs"""
    def __init__(self, max_size=500):
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.last_id = 0
    
    def add(self, level, source, message):
        with self.lock:
            self.last_id += 1
            entry = {
                'id': self.last_id,
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'level': level,
                'source': source,
                'message': message
            }
            self.buffer.append(entry)
            return entry
    
    def get_all(self):
        with self.lock:
            return list(self.buffer)
    
    def get_since(self, since_id):
        with self.lock:
            return [e for e in self.buffer if e['id'] > since_id]
    
    def clear(self):
        with self.lock:
            self.buffer.clear()
            self.last_id = 0

log_buffer = LogBuffer()

def debug_print(message, level='INFO', source='DEBUG'):
    """Print to console and add to log buffer for frontend visibility"""
    # Strip ANSI codes for the buffer
    clean_message = re.sub(r'\033\[[0-9;]*m', '', message)
    log_buffer.add(level, source, clean_message)
    # Still print to console with colors
    print(message)

# ==================================================
# COMPREHENSIVE LANGUAGE MARKERS FOR DETECTION
# ==================================================
# These markers are used to detect if text is in a specific language.
# For Latin-alphabet languages: common words with spaces around them
# For Asian languages: common characters/particles (no spaces needed)

LANGUAGE_MARKERS = {
    'en': {
        'type': 'word',  # Uses space-separated words
        'markers': [
            # Articles & Determiners
            ' the ', ' a ', ' an ', ' this ', ' that ', ' these ', ' those ',
            ' some ', ' any ', ' no ', ' every ', ' each ', ' all ', ' both ',
            # Pronouns
            ' i ', ' you ', ' he ', ' she ', ' it ', ' we ', ' they ',
            ' me ', ' him ', ' her ', ' us ', ' them ', ' my ', ' your ',
            ' his ', ' its ', ' our ', ' their ', ' mine ', ' yours ',
            ' who ', ' whom ', ' whose ', ' which ', ' what ',
            # Common verbs (conjugated)
            ' is ', ' are ', ' was ', ' were ', ' be ', ' been ', ' being ',
            ' have ', ' has ', ' had ', ' having ', ' do ', ' does ', ' did ',
            ' will ', ' would ', ' shall ', ' should ', ' can ', ' could ',
            ' may ', ' might ', ' must ', ' need ', ' dare ', ' ought ',
            ' said ', ' says ', ' told ', ' asked ', ' answered ', ' replied ',
            ' went ', ' came ', ' got ', ' made ', ' took ', ' gave ', ' knew ',
            ' thought ', ' felt ', ' saw ', ' heard ', ' seemed ', ' looked ',
            # Prepositions
            ' in ', ' on ', ' at ', ' by ', ' for ', ' with ', ' about ',
            ' against ', ' between ', ' into ', ' through ', ' during ',
            ' before ', ' after ', ' above ', ' below ', ' from ', ' up ',
            ' down ', ' out ', ' off ', ' over ', ' under ', ' again ',
            # Conjunctions
            ' and ', ' but ', ' or ', ' nor ', ' so ', ' yet ', ' because ',
            ' although ', ' while ', ' if ', ' unless ', ' until ', ' when ',
            ' where ', ' whether ', ' however ', ' therefore ', ' moreover ',
            # Adverbs
            ' not ', ' very ', ' really ', ' just ', ' also ', ' only ',
            ' even ', ' still ', ' already ', ' always ', ' never ', ' often ',
            ' sometimes ', ' usually ', ' here ', ' there ', ' now ', ' then ',
            # Common phrases/patterns
            ' of the ', ' to the ', ' in the ', ' on the ', ' at the ',
            ' and the ', ' for the ', ' with the ', ' from the ',
            ' there is ', ' there are ', ' there was ', ' there were ',
        ],
        'min_markers': 3,  # Minimum markers to consider text as this language
    },
    'es': {
        'type': 'word',
        'markers': [
            # Articles
            ' el ', ' la ', ' los ', ' las ', ' un ', ' una ', ' unos ', ' unas ',
            # Prepositions
            ' de ', ' del ', ' al ', ' en ', ' con ', ' por ', ' para ', ' sin ',
            ' sobre ', ' entre ', ' hacia ', ' desde ', ' hasta ', ' según ',
            ' durante ', ' mediante ', ' contra ', ' ante ', ' bajo ',
            # Pronouns
            ' yo ', ' tú ', ' él ', ' ella ', ' usted ', ' nosotros ', ' ellos ',
            ' ellas ', ' ustedes ', ' me ', ' te ', ' le ', ' nos ', ' les ',
            ' lo ', ' se ', ' mi ', ' tu ', ' su ', ' mis ', ' tus ', ' sus ',
            ' que ', ' quien ', ' cual ', ' cuyo ', ' donde ', ' como ', ' cuando ',
            # Common verbs
            ' es ', ' son ', ' era ', ' eran ', ' fue ', ' fueron ', ' ser ', ' sido ',
            ' está ', ' están ', ' estaba ', ' estuvo ', ' estar ', ' estado ',
            ' ha ', ' han ', ' había ', ' hubo ', ' haber ', ' habido ',
            ' tiene ', ' tienen ', ' tenía ', ' tuvo ', ' tener ', ' tenido ',
            ' hace ', ' hacen ', ' hacía ', ' hizo ', ' hacer ', ' hecho ',
            ' puede ', ' pueden ', ' podía ', ' pudo ', ' poder ', ' podido ',
            ' quiere ', ' quieren ', ' quería ', ' quiso ', ' querer ',
            ' dice ', ' dicen ', ' decía ', ' dijo ', ' decir ', ' dicho ',
            ' sabe ', ' saben ', ' sabía ', ' supo ', ' saber ', ' sabido ',
            ' ve ', ' ven ', ' veía ', ' vio ', ' ver ', ' visto ',
            ' va ', ' van ', ' iba ', ' fue ', ' ir ', ' ido ',
            # Conjunctions
            ' y ', ' e ', ' o ', ' u ', ' pero ', ' sino ', ' aunque ', ' porque ',
            ' pues ', ' como ', ' si ', ' cuando ', ' donde ', ' mientras ',
            # Adverbs
            ' no ', ' sí ', ' muy ', ' más ', ' menos ', ' bien ', ' mal ',
            ' ya ', ' aún ', ' todavía ', ' siempre ', ' nunca ', ' también ',
            ' solo ', ' además ', ' aquí ', ' allí ', ' ahora ', ' entonces ',
            # Common patterns
            ' de la ', ' de los ', ' de las ', ' en el ', ' en la ',
            ' a la ', ' a los ', ' por el ', ' por la ', ' con el ', ' con la ',
        ],
        'min_markers': 3,
    },
    'fr': {
        'type': 'word',
        'markers': [
            # Articles
            ' le ', ' la ', ' les ', ' un ', ' une ', ' des ', ' du ', ' de la ',
            " l'", " d'", " n'", " s'", " c'", " j'", " m'", " t'", " qu'",
            # Prepositions
            ' de ', ' à ', ' en ', ' dans ', ' sur ', ' sous ', ' avec ', ' sans ',
            ' pour ', ' par ', ' chez ', ' vers ', ' entre ', ' contre ',
            # Pronouns
            ' je ', ' tu ', ' il ', ' elle ', ' on ', ' nous ', ' vous ', ' ils ', ' elles ',
            ' me ', ' te ', ' se ', ' lui ', ' leur ', ' moi ', ' toi ', ' soi ',
            ' ce ', ' cet ', ' cette ', ' ces ', ' qui ', ' que ', ' quoi ', ' dont ', ' où ',
            # Common verbs
            ' est ', ' sont ', ' était ', ' étaient ', ' fut ', ' être ', ' été ',
            ' a ', ' ont ', ' avait ', ' avaient ', ' eut ', ' avoir ', ' eu ',
            ' fait ', ' font ', ' faisait ', ' fit ', ' faire ',
            ' dit ', ' disent ', ' disait ', ' dire ',
            ' peut ', ' peuvent ', ' pouvait ', ' pouvoir ', ' pu ',
            ' veut ', ' veulent ', ' voulait ', ' vouloir ', ' voulu ',
            ' sait ', ' savent ', ' savait ', ' savoir ', ' su ',
            ' voit ', ' voient ', ' voyait ', ' voir ', ' vu ',
            ' va ', ' vont ', ' allait ', ' aller ', ' allé ',
            # Conjunctions
            ' et ', ' ou ', ' mais ', ' donc ', ' car ', ' ni ', ' or ',
            ' si ', ' que ', ' quand ', ' comme ', ' parce ', ' puisque ',
            # Adverbs/Negation
            ' ne ', ' pas ', ' plus ', ' jamais ', ' rien ', ' personne ',
            ' très ', ' bien ', ' mal ', ' peu ', ' beaucoup ', ' trop ',
            ' aussi ', ' encore ', ' toujours ', ' déjà ', ' ici ', ' là ',
            # Common patterns
            " c'est ", " c'était ", " il y a ", " il y avait ",
        ],
        'min_markers': 3,
    },
    'de': {
        'type': 'word',
        'markers': [
            # Articles
            ' der ', ' die ', ' das ', ' den ', ' dem ', ' des ',
            ' ein ', ' eine ', ' einen ', ' einem ', ' einer ', ' eines ',
            # Prepositions
            ' in ', ' an ', ' auf ', ' für ', ' mit ', ' von ', ' zu ', ' bei ',
            ' nach ', ' über ', ' unter ', ' vor ', ' hinter ', ' neben ',
            ' zwischen ', ' durch ', ' gegen ', ' ohne ', ' um ', ' aus ',
            # Pronouns
            ' ich ', ' du ', ' er ', ' sie ', ' es ', ' wir ', ' ihr ',
            ' mich ', ' dich ', ' sich ', ' uns ', ' euch ', ' ihm ', ' ihn ',
            ' mir ', ' dir ', ' mein ', ' dein ', ' sein ', ' unser ', ' euer ',
            ' wer ', ' was ', ' welch ', ' dessen ', ' deren ',
            # Common verbs
            ' ist ', ' sind ', ' war ', ' waren ', ' sein ', ' gewesen ',
            ' hat ', ' haben ', ' hatte ', ' hatten ', ' gehabt ',
            ' wird ', ' werden ', ' wurde ', ' wurden ', ' geworden ',
            ' kann ', ' können ', ' konnte ', ' konnten ', ' gekonnt ',
            ' muss ', ' müssen ', ' musste ', ' gemusst ',
            ' will ', ' wollen ', ' wollte ', ' gewollt ',
            ' soll ', ' sollen ', ' sollte ', ' gesollt ',
            ' sagt ', ' sagen ', ' sagte ', ' gesagt ',
            ' geht ', ' gehen ', ' ging ', ' gegangen ',
            ' kommt ', ' kommen ', ' kam ', ' gekommen ',
            ' macht ', ' machen ', ' machte ', ' gemacht ',
            # Conjunctions
            ' und ', ' oder ', ' aber ', ' denn ', ' weil ', ' dass ', ' daß ',
            ' wenn ', ' ob ', ' als ', ' während ', ' obwohl ', ' damit ',
            # Adverbs
            ' nicht ', ' auch ', ' nur ', ' noch ', ' schon ', ' sehr ',
            ' immer ', ' nie ', ' oft ', ' hier ', ' dort ', ' jetzt ', ' dann ',
        ],
        'min_markers': 3,
    },
    'it': {
        'type': 'word',
        'markers': [
            # Articles
            ' il ', ' lo ', ' la ', ' i ', ' gli ', ' le ',
            ' un ', ' uno ', ' una ', " un'", ' del ', ' dello ', ' della ',
            ' dei ', ' degli ', ' delle ', ' al ', ' allo ', ' alla ',
            " l'", " d'", " c'", " n'", " s'",
            # Prepositions
            ' di ', ' a ', ' da ', ' in ', ' con ', ' su ', ' per ', ' tra ', ' fra ',
            ' sopra ', ' sotto ', ' dentro ', ' fuori ', ' verso ', ' contro ',
            # Pronouns
            ' io ', ' tu ', ' lui ', ' lei ', ' noi ', ' voi ', ' loro ',
            ' mi ', ' ti ', ' ci ', ' vi ', ' si ', ' lo ', ' la ', ' li ',
            ' me ', ' te ', ' sé ', ' che ', ' chi ', ' cui ', ' quale ',
            # Common verbs
            ' è ', ' sono ', ' era ', ' erano ', ' fu ', ' furono ', ' essere ', ' stato ',
            ' ha ', ' hanno ', ' aveva ', ' avevano ', ' ebbe ', ' avere ', ' avuto ',
            ' fa ', ' fanno ', ' faceva ', ' fece ', ' fare ', ' fatto ',
            ' dice ', ' dicono ', ' diceva ', ' disse ', ' dire ', ' detto ',
            ' può ', ' possono ', ' poteva ', ' potere ', ' potuto ',
            ' vuole ', ' vogliono ', ' voleva ', ' volere ', ' voluto ',
            ' sa ', ' sanno ', ' sapeva ', ' sapere ', ' saputo ',
            ' vede ', ' vedono ', ' vedeva ', ' vedere ', ' visto ',
            ' va ', ' vanno ', ' andava ', ' andare ', ' andato ',
            # Conjunctions
            ' e ', ' o ', ' ma ', ' però ', ' perché ', ' poiché ', ' quando ',
            ' se ', ' come ', ' mentre ', ' sebbene ', ' affinché ',
            # Adverbs
            ' non ', ' sì ', ' molto ', ' poco ', ' più ', ' meno ', ' bene ', ' male ',
            ' già ', ' ancora ', ' sempre ', ' mai ', ' anche ', ' solo ',
            ' qui ', ' qua ', ' lì ', ' là ', ' ora ', ' adesso ', ' poi ', ' allora ',
        ],
        'min_markers': 3,
    },
    'pt': {
        'type': 'word',
        'markers': [
            # Articles
            ' o ', ' a ', ' os ', ' as ', ' um ', ' uma ', ' uns ', ' umas ',
            ' do ', ' da ', ' dos ', ' das ', ' no ', ' na ', ' nos ', ' nas ',
            ' ao ', ' à ', ' aos ', ' às ', ' pelo ', ' pela ', ' pelos ', ' pelas ',
            # Prepositions
            ' de ', ' em ', ' com ', ' por ', ' para ', ' sem ', ' sob ', ' sobre ',
            ' entre ', ' contra ', ' desde ', ' até ', ' após ', ' durante ',
            # Pronouns
            ' eu ', ' tu ', ' ele ', ' ela ', ' você ', ' nós ', ' eles ', ' elas ', ' vocês ',
            ' me ', ' te ', ' se ', ' lhe ', ' nos ', ' vos ', ' lhes ',
            ' meu ', ' minha ', ' teu ', ' tua ', ' seu ', ' sua ', ' nosso ', ' nossa ',
            ' que ', ' quem ', ' qual ', ' cujo ', ' onde ', ' como ', ' quando ',
            # Common verbs
            ' é ', ' são ', ' era ', ' eram ', ' foi ', ' foram ', ' ser ', ' sido ',
            ' está ', ' estão ', ' estava ', ' esteve ', ' estar ', ' estado ',
            ' tem ', ' têm ', ' tinha ', ' teve ', ' ter ', ' tido ',
            ' há ', ' havia ', ' houve ', ' haver ', ' havido ',
            ' faz ', ' fazem ', ' fazia ', ' fez ', ' fazer ', ' feito ',
            ' pode ', ' podem ', ' podia ', ' pôde ', ' poder ', ' podido ',
            ' quer ', ' querem ', ' queria ', ' quis ', ' querer ', ' querido ',
            ' diz ', ' dizem ', ' dizia ', ' disse ', ' dizer ', ' dito ',
            ' sabe ', ' sabem ', ' sabia ', ' soube ', ' saber ', ' sabido ',
            ' vê ', ' veem ', ' via ', ' viu ', ' ver ', ' visto ',
            ' vai ', ' vão ', ' ia ', ' foi ', ' ir ', ' ido ',
            # Conjunctions
            ' e ', ' ou ', ' mas ', ' porém ', ' contudo ', ' todavia ', ' porque ',
            ' pois ', ' como ', ' se ', ' quando ', ' enquanto ', ' embora ',
            # Adverbs
            ' não ', ' sim ', ' muito ', ' pouco ', ' mais ', ' menos ', ' bem ', ' mal ',
            ' já ', ' ainda ', ' sempre ', ' nunca ', ' também ', ' só ', ' apenas ',
            ' aqui ', ' ali ', ' lá ', ' agora ', ' então ', ' depois ', ' antes ',
        ],
        'min_markers': 3,
    },
    'ru': {
        'type': 'word',
        'markers': [
            # Prepositions and particles
            ' в ', ' на ', ' с ', ' к ', ' у ', ' о ', ' за ', ' из ', ' по ', ' от ',
            ' до ', ' для ', ' при ', ' без ', ' под ', ' над ', ' между ', ' через ',
            # Pronouns
            ' я ', ' ты ', ' он ', ' она ', ' оно ', ' мы ', ' вы ', ' они ',
            ' мне ', ' тебе ', ' ему ', ' ей ', ' нам ', ' вам ', ' им ',
            ' меня ', ' тебя ', ' его ', ' её ', ' нас ', ' вас ', ' их ',
            ' мой ', ' твой ', ' его ', ' её ', ' наш ', ' ваш ', ' свой ',
            ' кто ', ' что ', ' какой ', ' который ', ' чей ', ' где ', ' когда ',
            ' это ', ' этот ', ' эта ', ' эти ', ' тот ', ' та ', ' те ',
            # Common verbs
            ' был ', ' была ', ' было ', ' были ', ' есть ', ' быть ', ' будет ',
            ' имеет ', ' имеют ', ' иметь ', ' имел ',
            ' может ', ' могут ', ' мог ', ' могла ', ' мочь ',
            ' хочет ', ' хотят ', ' хотел ', ' хотела ', ' хотеть ',
            ' знает ', ' знают ', ' знал ', ' знала ', ' знать ',
            ' видит ', ' видят ', ' видел ', ' видела ', ' видеть ',
            ' говорит ', ' говорят ', ' говорил ', ' сказал ', ' сказала ',
            ' делает ', ' делают ', ' делал ', ' делала ', ' делать ', ' сделать ',
            ' идёт ', ' идут ', ' шёл ', ' шла ', ' идти ', ' пойти ',
            # Conjunctions
            ' и ', ' а ', ' но ', ' или ', ' да ', ' ни ', ' же ', ' ли ',
            ' что ', ' чтобы ', ' если ', ' когда ', ' пока ', ' хотя ', ' потому ',
            # Adverbs
            ' не ', ' ещё ', ' уже ', ' очень ', ' так ', ' как ', ' тоже ', ' также ',
            ' всё ', ' все ', ' только ', ' ещё ', ' даже ', ' здесь ', ' там ',
            ' сейчас ', ' тогда ', ' потом ', ' теперь ', ' всегда ', ' никогда ',
        ],
        'min_markers': 3,
    },
    'zh': {
        'type': 'character',  # Chinese uses characters, not space-separated words
        'markers': [
            # Common particles and grammatical markers
            '的', '了', '是', '在', '有', '和', '与', '或', '但', '而',
            '我', '你', '他', '她', '它', '们', '这', '那', '什么', '怎么',
            '不', '也', '都', '就', '还', '又', '才', '已', '很', '太',
            '着', '过', '地', '得', '吗', '呢', '吧', '啊', '呀', '哦',
            '个', '些', '里', '上', '下', '中', '前', '后', '来', '去',
            '说', '看', '想', '知', '要', '会', '能', '可', '应', '该',
            '人', '时', '年', '月', '日', '天', '事', '话', '问', '答',
            '大', '小', '多', '少', '高', '低', '长', '短', '好', '坏',
            '为', '因', '所', '被', '把', '让', '给', '从', '到', '向',
            '如果', '虽然', '但是', '因为', '所以', '而且', '或者', '不过',
        ],
        'min_markers': 5,  # Need more markers for Asian languages
    },
    'ja': {
        'type': 'character',  # Japanese uses characters (hiragana, katakana, kanji)
        'markers': [
            # Hiragana particles and common words
            'の', 'は', 'が', 'を', 'に', 'で', 'と', 'も', 'や', 'か',
            'へ', 'より', 'から', 'まで', 'など', 'だけ', 'しか', 'ばかり',
            'です', 'ます', 'でした', 'ました', 'である', 'ではない',
            'ない', 'なかった', 'ある', 'あった', 'いる', 'いた',
            'この', 'その', 'あの', 'どの', 'これ', 'それ', 'あれ', 'どれ',
            'こと', 'もの', 'ところ', 'とき', 'ため', 'よう', 'ほう',
            'する', 'した', 'して', 'される', 'された', 'させる',
            'なる', 'なった', 'なって', 'できる', 'できた',
            'いう', 'いった', 'おもう', 'おもった', 'みる', 'みた',
            'くる', 'きた', 'いく', 'いった', 'くれる', 'もらう',
            'という', 'として', 'について', 'によって', 'に対して',
            # Common kanji compounds
            '私', '彼', '彼女', '人', '時', '事', '物', '所', '方', '者',
            '言', '思', '見', '知', '聞', '読', '書', '話', '考', '感',
            '日本', '今日', '明日', '昨日', '今年', '来年', '去年',
        ],
        'min_markers': 5,
    },
    'ko': {
        'type': 'character',  # Korean uses Hangul characters
        'markers': [
            # Common particles and endings
            '은', '는', '이', '가', '을', '를', '의', '에', '에서', '로',
            '으로', '와', '과', '하고', '랑', '이랑', '도', '만', '부터', '까지',
            '이다', '입니다', '이에요', '예요', '였다', '였습니다',
            '하다', '합니다', '해요', '했다', '했습니다', '하는',
            '있다', '있습니다', '있어요', '없다', '없습니다', '없어요',
            '이것', '그것', '저것', '여기', '거기', '저기', '어디',
            '나', '너', '그', '그녀', '우리', '그들', '저', '제',
            '수', '것', '때', '곳', '사람', '말', '일', '생각',
            '하지', '않다', '않습니다', '못하다', '되다', '됩니다',
            '보다', '오다', '가다', '주다', '받다', '알다', '모르다',
            '그리고', '그러나', '하지만', '그래서', '왜냐하면', '만약',
            '아주', '매우', '너무', '정말', '진짜', '많이', '조금',
        ],
        'min_markers': 5,
    },
}

def detect_language_markers(text: str, lang_code: str) -> tuple:
    """
    Detect how many language markers are present in text.
    Returns (marker_count, total_markers_checked, ratio)
    """
    if lang_code not in LANGUAGE_MARKERS:
        return (0, 0, 0.0)
    
    lang_info = LANGUAGE_MARKERS[lang_code]
    markers = lang_info['markers']
    marker_type = lang_info['type']
    
    text_lower = text.lower()
    marker_count = 0
    
    if marker_type == 'word':
        # For space-separated languages, look for word patterns
        for marker in markers:
            if marker.lower() in text_lower:
                marker_count += 1
    else:
        # For character-based languages (Chinese, Japanese, Korean)
        for marker in markers:
            if marker in text:  # Case-sensitive for Asian characters
                marker_count += 1
    
    total_markers = len(markers)
    ratio = marker_count / total_markers if total_markers > 0 else 0.0
    
    return (marker_count, total_markers, ratio)

# ==================================================

# ANSI Color codes for console output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BG_RED + Colors.WHITE,
    }
    
    # Map for source names (without ANSI codes for buffer)
    SOURCE_MAP = {
        'app_logger': 'APP',
        'translation_logger': 'TRANS',
        'api_logger': 'API',
    }
    
    def format(self, record):
        # Add color based on level
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        
        # Format timestamp
        timestamp = self.formatTime(record, '%H:%M:%S')
        
        # Get logger name suffix
        name_map = {
            'app_logger': f'{Colors.BLUE}[APP]{Colors.RESET}',
            'translation_logger': f'{Colors.MAGENTA}[TRANS]{Colors.RESET}',
            'api_logger': f'{Colors.CYAN}[API]{Colors.RESET}',
        }
        logger_tag = name_map.get(record.name, f'[{record.name}]')
        
        # Format level
        level_name = f'{color}{record.levelname:8}{Colors.RESET}'
        
        # Format message
        message = record.getMessage()
        
        # Also add to the in-memory buffer for the frontend
        source = self.SOURCE_MAP.get(record.name, record.name)
        log_buffer.add(record.levelname, source, message)
        
        return f'{Colors.GRAY}{timestamp}{Colors.RESET} {logger_tag} {level_name} {message}'

# Logger setup
class AppLogger:
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        self.app_logger = self._setup_logger(
            'app_logger',
            os.path.join(log_dir, 'app.log')
        )
        
        self.translation_logger = self._setup_logger(
            'translation_logger',
            os.path.join(log_dir, 'translations.log')
        )
        
        self.api_logger = self._setup_logger(
            'api_logger',
            os.path.join(log_dir, 'api.log')
        )
        
        # Print startup banner
        if VERBOSE_DEBUG:
            self._print_banner()
    
    def _print_banner(self):
        print(f"\n{Colors.CYAN}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}  📚 BOOK TRANSLATOR - VERBOSE DEBUG MODE{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")
        print(f"{Colors.YELLOW}  All operations will be logged to console{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}\n")

    def _setup_logger(self, name, log_file):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG if VERBOSE_DEBUG else logging.INFO)
        
        # File handler (always INFO level)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler (DEBUG level when verbose)
        if VERBOSE_DEBUG:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(ColoredFormatter())
            logger.addHandler(console_handler)
        
        return logger

# Initialize logger
logger = AppLogger()

# Monitoring setup
@dataclass
class TranslationMetrics:
    total_requests: int = 0
    successful_translations: int = 0
    failed_translations: int = 0
    average_translation_time: float = 0
    translation_times: deque = field(default_factory=lambda: deque(maxlen=100))

class AppMonitor:
    def __init__(self):
        self.metrics = TranslationMetrics()
        self._lock = threading.Lock()
        self.start_time = time.time()
        
    def record_translation_attempt(self, success: bool, translation_time: float):
        with self._lock:
            self.metrics.total_requests += 1
            if success:
                self.metrics.successful_translations += 1
                self.metrics.translation_times.append(translation_time)
                self.metrics.average_translation_time = (
                    sum(self.metrics.translation_times) / len(self.metrics.translation_times)
                )
            else:
                self.metrics.failed_translations += 1
    
    def get_system_metrics(self) -> Dict:
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'uptime': time.time() - self.start_time
        }
    
    def get_metrics(self) -> Dict:
        with self._lock:
            metrics_data = {
                'translation_metrics': {
                    'total_requests': self.metrics.total_requests,
                    'successful_translations': self.metrics.successful_translations,
                    'failed_translations': self.metrics.failed_translations,
                    'average_translation_time': self.metrics.average_translation_time
                },
                'system_metrics': self.get_system_metrics()
            }
            
            if self.metrics.total_requests > 0:
                metrics_data['translation_metrics']['success_rate'] = (
                    self.metrics.successful_translations / self.metrics.total_requests * 100
                )
            else:
                metrics_data['translation_metrics']['success_rate'] = 0
                
            return metrics_data

# Initialize monitor
monitor = AppMonitor()

# Translation cache setup
class TranslationCache:
    def __init__(self, db_path: str = CACHE_DB_PATH):
        self.db_path = db_path
        self._init_cache_db()
    
    def _init_cache_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translation_cache (
                    hash_key TEXT PRIMARY KEY,
                    source_lang TEXT,
                    target_lang TEXT,
                    original_text TEXT,
                    translated_text TEXT,
                    machine_translation TEXT,
                    created_at TIMESTAMP,
                    last_used TIMESTAMP
                )
            ''')

    def _generate_hash(self, text: str, source_lang: str, target_lang: str, model: str = "", context_hash: str = "") -> str:
        """Generate a unique hash including context to avoid cache collisions."""
        key = f"{text}:{source_lang}:{target_lang}:{model}:{context_hash}".encode('utf-8')
        return hashlib.sha256(key).hexdigest()
    
    def get_cached_translation(self, text: str, source_lang: str, target_lang: str, model: str = "", context_hash: str = "") -> Optional[Dict[str, str]]:
        hash_key = self._generate_hash(text, source_lang, target_lang, model, context_hash)
        
        if VERBOSE_DEBUG:
            logger.app_logger.debug(f"🔍 Cache lookup: hash={hash_key[:16]}... model={model} ctx={context_hash[:8] if context_hash else 'none'}")
        
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('''
                SELECT translated_text, machine_translation
                FROM translation_cache
                WHERE hash_key = ?
            ''', (hash_key,))
            
            result = cur.fetchone()
            if result:
                if VERBOSE_DEBUG:
                    logger.app_logger.debug(f"   💾 Cache HIT! ({len(result[0])} chars)")
                conn.execute('''
                    UPDATE translation_cache
                    SET last_used = CURRENT_TIMESTAMP
                    WHERE hash_key = ?
                ''', (hash_key,))
                return {
                    'translated_text': result[0],
                    'machine_translation': result[1]
                }
        
        if VERBOSE_DEBUG:
            logger.app_logger.debug(f"   ❌ Cache MISS")
        return None
    
    def cache_translation(self, text: str, translated_text: str, machine_translation: str, 
                         source_lang: str, target_lang: str, model: str = "", context_hash: str = ""):
        hash_key = self._generate_hash(text, source_lang, target_lang, model, context_hash)
        
        if VERBOSE_DEBUG:
            logger.app_logger.debug(f"💾 Caching translation: hash={hash_key[:16]}... ({len(translated_text)} chars)")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO translation_cache
                (hash_key, source_lang, target_lang, original_text, translated_text, 
                 machine_translation, created_at, last_used)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (hash_key, source_lang, target_lang, text, translated_text, machine_translation))
    
    def cleanup_old_entries(self, days: int = 30):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"DELETE FROM translation_cache WHERE last_used < datetime('now', '-{days} days')"
            )
    
    def clear_all(self):
        """Clear all cached translations. Useful when fixing bugs or testing."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM translation_cache")
            logger.app_logger.info("Translation cache cleared")

# Initialize cache
cache = TranslationCache()

# Terminology Manager
class TerminologyManager:
    """Manages consistent terminology across translation chunks"""
    
    def __init__(self):
        self.terms = {}  # {original_term: translated_term}
        self.proper_nouns = set()
    
    def extract_proper_nouns(self, text: str) -> List[str]:
        """Extract proper nouns (capitalized words/phrases)"""
        # Match capitalized words that are not at sentence start
        pattern = r'(?<!^)(?<![.!?]\s)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        nouns = re.findall(pattern, text, re.MULTILINE)
        return list(set(nouns))
    
    def add_term(self, original: str, translated: str):
        """Add a term to the terminology dictionary"""
        self.terms[original] = translated
    
    def get_term(self, original: str) -> Optional[str]:
        """Get translated term if it exists"""
        return self.terms.get(original)
    
    def ensure_consistency(self, text: str, chunk_terms: Dict[str, str]) -> str:
        """Apply consistent terminology to text"""
        for original, translated in chunk_terms.items():
            if original in self.terms and self.terms[original] != translated:
                # Use consistent term from previous chunks
                text = text.replace(translated, self.terms[original])
            else:
                self.terms[original] = translated
        return text
    
    def get_terminology_context(self) -> str:
        """Generate context string with important terms"""
        if not self.terms:
            return ""
        
        term_list = [f"{orig} -> {trans}" for orig, trans in list(self.terms.items())[:10]]
        return "Important terms: " + ", ".join(term_list)

# Error handling setup
class TranslationError(Exception):
    pass

def with_error_handling(f: Callable):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.Timeout as e:
            logger.app_logger.error(f"Timeout error: {str(e)}")
            raise TranslationError("Translation service timeout")
        except requests.RequestException as e:
            logger.app_logger.error(f"Request error: {str(e)}")
            raise TranslationError("Translation service unavailable")
        except sqlite3.Error as e:
            logger.app_logger.error(f"Database error: {str(e)}")
            raise TranslationError("Database error occurred")
        except Exception as e:
            logger.app_logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
            raise TranslationError("An unexpected error occurred")
    return wrapper

# Initialize database
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript('''
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS translations;
            
            CREATE TABLE translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0,
                current_chunk INTEGER DEFAULT 0,
                total_chunks INTEGER DEFAULT 0,
                original_text TEXT,
                machine_translation TEXT,
                translated_text TEXT,
                detected_language TEXT,
                genre TEXT DEFAULT 'unknown',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT
            );

            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                translation_id INTEGER,
                chunk_number INTEGER,
                original_text TEXT,
                machine_translation TEXT,
                translated_text TEXT,
                status TEXT,
                error_message TEXT,
                attempts INTEGER DEFAULT 0,
                FOREIGN KEY (translation_id) REFERENCES translations (id)
            );
        ''')

init_db()


class BookTranslator:
    def __init__(self, model_name: str = "llama3.3:70b-instruct-q2_K", chunk_size: int = 1000):
        self.model_name = model_name
        self.api_url = "http://localhost:11434/api/generate"
        self.chunk_size = chunk_size
        self.session = requests.Session()
        self.session.mount('http://', requests.adapters.HTTPAdapter(
            max_retries=3,
            pool_connections=10,
            pool_maxsize=10
        ))
        self.terminology = TerminologyManager()
        
        # Note: Ollama should be running separately
        # Don't try to start it automatically

    def _clean_translation_response(self, translation: str, previous_chunk: str) -> str:
        """
        Clean the LLM response to remove any accidentally repeated content 
        from the previous chunk that the LLM might have included.
        """
        if not previous_chunk or not translation:
            return translation.strip()
        
        translation = translation.strip()
        
        # Remove any leading content that matches the end of the previous chunk
        # This handles cases where the LLM includes context from the previous paragraph
        prev_lines = previous_chunk.strip().split('\n')
        
        # Check if translation starts with repeated content from previous chunk
        for i in range(min(5, len(prev_lines))):  # Check last 5 lines of previous
            check_text = '\n'.join(prev_lines[-(i+1):]).strip()
            if len(check_text) > 50 and translation.startswith(check_text):
                # Remove the duplicated content
                translation = translation[len(check_text):].strip()
                logger.translation_logger.info(f"Removed {len(check_text)} chars of duplicate prefix")
                break
        
        # Also check for partial sentence duplicates at the start
        if len(prev_lines) > 0:
            last_prev_line = prev_lines[-1].strip()
            if len(last_prev_line) > 30:
                # Check if translation starts with a significant portion of the last line
                for check_len in range(len(last_prev_line), 30, -10):
                    check_segment = last_prev_line[-check_len:]
                    if translation.startswith(check_segment):
                        translation = translation[len(check_segment):].strip()
                        logger.translation_logger.info(f"Removed {len(check_segment)} chars of partial duplicate")
                        break
        
        # Remove common LLM prefixes/suffixes that shouldn't be in the output
        unwanted_prefixes = [
            "Here is the translation:",
            "Here's the translation:",
            "Translation:",
            "Translated text:",
            "**Translation:**",
            "---",
        ]
        for prefix in unwanted_prefixes:
            if translation.lower().startswith(prefix.lower()):
                translation = translation[len(prefix):].strip()
        
        return translation.strip()
    
    def _is_likely_translated(self, original: str, translated: str, source_lang: str, target_lang: str) -> bool:
        """
        Check if the translated text is actually different from the original.
        Returns True if translation appears to have occurred.
        Uses comprehensive language markers for accurate detection.
        """
        if VERBOSE_DEBUG:
            logger.translation_logger.debug(f"🔍 Validating translation: orig={len(original)} chars, trans={len(translated)} chars")
        
        if not translated or not original:
            if VERBOSE_DEBUG:
                logger.translation_logger.debug(f"   ❌ Empty text - validation failed")
            return False
        
        # If same language, can't easily verify
        if source_lang == target_lang:
            if VERBOSE_DEBUG:
                logger.translation_logger.debug(f"   ✓ Same language pair - skipping validation")
            return True
        
        # If translated text is very short, accept it
        if len(translated) < 50:
            if VERBOSE_DEBUG:
                logger.translation_logger.debug(f"   ✓ Short text - accepting")
            return True
        
        # Normalize texts for comparison (for Latin-alphabet languages)
        orig_normalized = ' '.join(original.lower().split())
        trans_normalized = ' '.join(translated.lower().split())
        
        # If they're identical, translation definitely failed
        if orig_normalized == trans_normalized:
            if VERBOSE_DEBUG:
                logger.translation_logger.debug(f"   ❌ Texts are identical - translation failed!")
            return False
        
        # For Latin-alphabet languages: Calculate word similarity
        if source_lang not in ['zh', 'ja', 'ko']:
            orig_words = set(orig_normalized.split())
            trans_words = set(trans_normalized.split())
            
            if len(orig_words) > 0:
                common_words = orig_words.intersection(trans_words)
                similarity = len(common_words) / len(orig_words)
                
                if VERBOSE_DEBUG:
                    logger.translation_logger.debug(f"   📊 Word similarity: {similarity:.1%} ({len(common_words)}/{len(orig_words)} common words)")
                
                # Reject if similarity is very high (>65%) - tightened threshold
                if similarity > 0.65:
                    logger.translation_logger.warning(f"⚠️ Very high similarity ({similarity:.2%}) suggests translation may have failed")
                    return False
        
        # Use comprehensive language markers to check if source language remains
        if source_lang in LANGUAGE_MARKERS:
            source_count, _, source_ratio = detect_language_markers(translated, source_lang)
            lang_info = LANGUAGE_MARKERS[source_lang]
            min_markers = lang_info['min_markers']
            
            # Calculate threshold based on text length
            word_count = len(translated.split()) if lang_info['type'] == 'word' else len(translated)
            
            # Dynamic threshold: more lenient for short texts, stricter for long texts
            if lang_info['type'] == 'word':
                # For word-based languages
                threshold = max(min_markers, min(8, word_count // 15))
            else:
                # For character-based languages (higher threshold)
                threshold = max(min_markers + 2, min(12, word_count // 30))
            
            if VERBOSE_DEBUG:
                logger.translation_logger.debug(f"   📊 Source markers in translation: {source_count} (threshold: {threshold})")
            
            if source_count > threshold:
                logger.translation_logger.warning(f"Found {source_count} {source_lang.upper()} markers in 'translated' text (threshold: {threshold})")
                return False
        
        # Also verify target language markers are present (positive check)
        if target_lang in LANGUAGE_MARKERS:
            target_count, _, _ = detect_language_markers(translated, target_lang)
            target_min = LANGUAGE_MARKERS[target_lang]['min_markers']
            
            if VERBOSE_DEBUG:
                logger.translation_logger.debug(f"   📊 Target markers in translation: {target_count} (min expected: {target_min})")
            
            # If no target language markers at all, suspicious
            if target_count < target_min and len(translated) > 100:
                logger.translation_logger.warning(f"Only {target_count} {target_lang.upper()} markers found - translation may have failed")
                return False
        
        return True
    
    def _remove_duplicate_paragraphs(self, text: str) -> str:
        """
        Post-process the final translation to remove any duplicate paragraphs
        that may have been introduced during chunk translation.
        """
        paragraphs = text.split('\n\n')
        seen_paragraphs = {}  # key -> first occurrence index
        unique_paragraphs = []
        
        for idx, para in enumerate(paragraphs):
            para_stripped = para.strip()
            if not para_stripped:
                continue
            
            # Create a normalized version for comparison (lowercase, no extra spaces)
            normalized = ' '.join(para_stripped.lower().split())
            
            # Only check for duplicates if paragraph is long enough to be meaningful
            # Short paragraphs (< 100 chars) might legitimately repeat
            if len(normalized) < 100:
                unique_paragraphs.append(para_stripped)
                continue
            
            # Use first 150 chars as key to catch near-duplicates
            # but require exact match for longer paragraphs
            key = normalized[:150]
            
            if key not in seen_paragraphs:
                seen_paragraphs[key] = idx
                unique_paragraphs.append(para_stripped)
            else:
                # Only remove if it's a near-exact duplicate (not just similar start)
                # Check if the full normalized text is very similar
                prev_idx = seen_paragraphs[key]
                if len(normalized) > 150:
                    # For longer paragraphs, check if they're truly duplicates
                    logger.translation_logger.info(f"Removed duplicate paragraph (idx {idx}, first seen at {prev_idx}): {para_stripped[:50]}...")
                else:
                    # For medium paragraphs with same key, still remove
                    logger.translation_logger.info(f"Removed duplicate paragraph: {para_stripped[:50]}...")
        
        return '\n\n'.join(unique_paragraphs)

    def _detect_untranslated_content(self, text: str, source_lang: str, target_lang: str) -> tuple:
        """
        Detect paragraphs that appear to be in the source language (untranslated).
        Uses comprehensive LANGUAGE_MARKERS for accurate detection.
        Returns (cleaned_text, list_of_problematic_paragraphs)
        """
        if source_lang == target_lang:
            return text, []
        
        if source_lang not in LANGUAGE_MARKERS:
            # Can't detect for unsupported languages
            return text, []
        
        paragraphs = text.split('\n\n')
        cleaned_paragraphs = []
        problematic = []
        
        lang_info = LANGUAGE_MARKERS[source_lang]
        is_asian = lang_info['type'] == 'character'
        base_min_markers = lang_info['min_markers']
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Skip very short paragraphs (likely headers, names, titles)
            min_length = 15 if is_asian else 30
            if len(para) < min_length:
                cleaned_paragraphs.append(para)
                continue
            
            # Detect source language markers
            marker_count, total_markers, ratio = detect_language_markers(para, source_lang)
            
            # Calculate text size metric
            if is_asian:
                text_size = len(para)  # Character count for Asian languages
                # For Asian languages: threshold based on character count
                # ~50 chars = 3 markers, ~100 chars = 5 markers, ~200+ chars = 8 markers
                threshold = max(base_min_markers, min(10, text_size // 25))
            else:
                text_size = len(para.split())  # Word count for others
                # For word-based languages: threshold based on word count
                # 10-30 words = 3 markers, 30-60 words = 5 markers, 60+ words = 7 markers
                if text_size < 30:
                    threshold = base_min_markers
                elif text_size < 60:
                    threshold = base_min_markers + 2
                else:
                    threshold = base_min_markers + 4
            
            # Check if this paragraph seems to be in source language
            is_suspicious = False
            
            if marker_count >= threshold:
                # For word-based languages, also check marker density
                if is_asian:
                    # For Asian: if we find many markers, it's suspicious
                    is_suspicious = True
                else:
                    # For Latin: check ratio of markers to words
                    marker_ratio = marker_count / text_size if text_size > 0 else 0
                    if marker_ratio > 0.06:  # More than 6% of words are markers
                        is_suspicious = True
            
            if is_suspicious:
                logger.translation_logger.warning(
                    f"Detected possibly untranslated paragraph ({marker_count} {source_lang.upper()} markers, "
                    f"threshold: {threshold}): {para[:60]}..."
                )
                problematic.append(para)
                # Mark it so user can see it
                cleaned_paragraphs.append(f"[⚠️ POSIBLE TEXTO SIN TRADUCIR] {para}")
                continue
            
            cleaned_paragraphs.append(para)
        
        return '\n\n'.join(cleaned_paragraphs), problematic

    def split_into_chunks(self, text: str) -> list:
        """
        Split text into smaller chunks for translation.
        Ensures clean boundaries at paragraph level when possible,
        and adds chunk markers to help detect overlap issues.
        """
        MAX_LENGTH = 4000  # Reduced from 4500 for safety margin
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            para_length = len(paragraph)
            
            if para_length + current_length > MAX_LENGTH:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Handle very long paragraphs
                if para_length > MAX_LENGTH:
                    # Split by sentences more carefully
                    # Use regex to split on sentence boundaries
                    sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
                    sentences = re.split(sentence_pattern, paragraph)
                    
                    temp_chunk = []
                    temp_length = 0
                    
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if not sentence:
                            continue
                            
                        sent_length = len(sentence)
                        
                        # If single sentence is too long, split it by commas
                        if sent_length > MAX_LENGTH:
                            if temp_chunk:
                                chunks.append(' '.join(temp_chunk))
                                temp_chunk = []
                                temp_length = 0
                            
                            # Split very long sentence by clause boundaries
                            clauses = sentence.split(', ')
                            clause_chunk = []
                            clause_length = 0
                            
                            for clause in clauses:
                                if clause_length + len(clause) > MAX_LENGTH:
                                    if clause_chunk:
                                        chunks.append(', '.join(clause_chunk))
                                        clause_chunk = []
                                        clause_length = 0
                                clause_chunk.append(clause)
                                clause_length += len(clause) + 2
                            
                            if clause_chunk:
                                chunks.append(', '.join(clause_chunk))
                        elif temp_length + sent_length > MAX_LENGTH:
                            if temp_chunk:
                                chunks.append(' '.join(temp_chunk))
                                temp_chunk = []
                                temp_length = 0
                            temp_chunk.append(sentence)
                            temp_length = sent_length
                        else:
                            temp_chunk.append(sentence)
                            temp_length += sent_length + 1
                    
                    if temp_chunk:
                        chunks.append(' '.join(temp_chunk))
                else:
                    # Start new chunk with this paragraph
                    current_chunk.append(paragraph)
                    current_length = para_length
            else:
                current_chunk.append(paragraph)
                current_length += para_length + 2  # +2 for '\n\n'
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        # Log chunk info for debugging
        logger.translation_logger.info(f"Split text into {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            logger.translation_logger.info(f"  Chunk {i+1}: {len(chunk)} chars, starts with: {chunk[:50]}...")
        
        return chunks

    def translate_text(self, text: str, source_lang: str, target_lang: str, translation_id: int, genre: str = 'unknown'):
        start_time = time.time()
        success = False
        
        try:
            chunks = self.split_into_chunks(text)
            total_chunks = len(chunks)
            draft_translations = []  # Stage 1 results
            final_translations = []  # Stage 2 results
            self.terminology = TerminologyManager()
            
            # VERBOSE DEBUG: Print translation start banner
            if VERBOSE_DEBUG:
                debug_print(f"\n{'='*60}", 'INFO', 'TRANS')
                debug_print(f"📖 STARTING TRANSLATION #{translation_id}", 'INFO', 'TRANS')
                debug_print(f"{'='*60}", 'INFO', 'TRANS')
                debug_print(f"  📁 Total text: {len(text)} characters", 'INFO', 'TRANS')
                debug_print(f"  🔢 Chunks: {total_chunks}", 'INFO', 'TRANS')
                debug_print(f"  🌐 {source_lang} → {target_lang}", 'INFO', 'TRANS')
                debug_print(f"  📚 Genre: {genre}", 'INFO', 'TRANS')
                debug_print(f"  🤖 Model: {self.model_name}", 'INFO', 'TRANS')
                debug_print(f"{'='*60}\n", 'INFO', 'TRANS')
            
            logger.translation_logger.info(f"Starting translation {translation_id} with {total_chunks} chunks (genre: {genre})")
            
            # Update database with total chunks (2 stages)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    UPDATE translations 
                    SET total_chunks = ?, status = 'in_progress', genre = ?
                    WHERE id = ?
                ''', (total_chunks * 2, genre, translation_id))
            
            # STAGE 1: Primary translation with context
            logger.translation_logger.info("Stage 1: Primary LLM translation")
            if VERBOSE_DEBUG:
                debug_print(f"\n▶ STAGE 1: Primary Translation", 'INFO', 'TRANS')
                debug_print(f"{'─'*40}", 'INFO', 'TRANS')
            
            for i, chunk in enumerate(chunks, 1):
                try:
                    if VERBOSE_DEBUG:
                        debug_print(f"\n📝 Chunk {i}/{total_chunks} ({len(chunk)} chars)", 'INFO', 'TRANS')
                        debug_print(f"   Preview: {chunk[:80].replace(chr(10), ' ')}...", 'DEBUG', 'TRANS')
                    
                    # Get previous context FIRST (needed for context-aware caching)
                    previous_chunk = draft_translations[-1] if draft_translations else ""
                    # Generate a hash of the context to differentiate cached entries
                    context_hash = hashlib.sha256(previous_chunk.encode('utf-8')).hexdigest()[:16] if previous_chunk else ""
                    
                    # Check cache with context
                    cached_result = cache.get_cached_translation(chunk, source_lang, target_lang, self.model_name + "_stage1", context_hash)
                    if cached_result:
                        draft_translation = cached_result['machine_translation']
                        # Verify cached result is actually translated
                        if draft_translation.startswith("[TRANSLATION_FAILED") or not self._is_likely_translated(chunk, draft_translation, source_lang, target_lang):
                            logger.translation_logger.warning(f"Cached stage 1 chunk {i} appears untranslated, re-translating...")
                            if VERBOSE_DEBUG:
                                debug_print(f"   ⚠️ Cache invalid, re-translating...", 'WARNING', 'TRANS')
                            cached_result = None  # Force re-translation
                        else:
                            logger.translation_logger.info(f"Cache hit for stage 1 chunk {i}")
                            if VERBOSE_DEBUG:
                                debug_print(f"   💾 Cache HIT", 'INFO', 'TRANS')
                    
                    if not cached_result:
                        logger.translation_logger.info(f"Stage 1 translating chunk {i}/{total_chunks}")
                        if VERBOSE_DEBUG:
                            debug_print(f"   🔄 Translating...", 'INFO', 'TRANS')
                        
                        draft_translation = self.stage1_primary_translation(
                            text=chunk,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            previous_chunk=previous_chunk,
                            genre=genre
                        )
                        
                        if VERBOSE_DEBUG:
                            print(f" Done!")
                        
                        # Check if translation actually failed
                        if draft_translation.startswith("[TRANSLATION_FAILED"):
                            error_msg = f"Chunk {i} translation failed after all retries"
                            logger.translation_logger.error(error_msg)
                            if VERBOSE_DEBUG:
                                debug_print(f"   ❌ FAILED: {error_msg}", 'ERROR', 'TRANS')
                            raise Exception(error_msg)
                        
                        # Clean the response to avoid duplicates
                        draft_translation = self._clean_translation_response(draft_translation, previous_chunk)
                        
                        if VERBOSE_DEBUG:
                            debug_print(f"   ✓ Result: {draft_translation[:80].replace(chr(10), ' ')}...", 'DEBUG', 'TRANS')
                        
                        # Only cache if translation was successful
                        if self._is_likely_translated(chunk, draft_translation, source_lang, target_lang):
                            cache.cache_translation(
                                chunk, draft_translation, draft_translation,
                                source_lang, target_lang, self.model_name + "_stage1", context_hash
                            )
                        time.sleep(0.5)
                    
                    draft_translations.append(draft_translation)
                    
                    progress = (i / (total_chunks * 2)) * 100
                    yield {
                        'progress': progress,
                        'stage': 'primary_translation',
                        'original_text': '\n\n'.join(chunks),
                        'machine_translation': '\n\n'.join(draft_translations),
                        'current_chunk': i,
                        'total_chunks': total_chunks * 2
                    }
                    
                except Exception as e:
                    error_msg = f"Error in stage 1 chunk {i}: {str(e)}"
                    logger.translation_logger.error(error_msg)
                    logger.translation_logger.error(traceback.format_exc())
                    raise Exception(error_msg)
            
            # STAGE 2: Reflection and improvement
            logger.translation_logger.info("Stage 2: Reflection and improvement")
            if VERBOSE_DEBUG:
                debug_print(f"\n▶ STAGE 2: Reflection & Improvement", 'INFO', 'TRANS')
                debug_print(f"{'─'*40}", 'INFO', 'TRANS')
            
            for i, (original_chunk, draft_chunk) in enumerate(zip(chunks, draft_translations), 1):
                try:
                    if VERBOSE_DEBUG:
                        debug_print(f"\n🔧 Improving Chunk {i}/{total_chunks}", 'INFO', 'TRANS')
                    
                    # Get previous context FIRST (needed for context-aware caching)
                    previous_final = final_translations[-1] if final_translations else ""
                    # Generate a hash of the context to differentiate cached entries
                    context_hash = hashlib.sha256(previous_final.encode('utf-8')).hexdigest()[:16] if previous_final else ""
                    
                    # Check cache with context
                    cached_result = cache.get_cached_translation(original_chunk, source_lang, target_lang, self.model_name + "_stage2", context_hash)
                    if cached_result:
                        final_translation = cached_result['translated_text']
                        # Verify cached result is actually translated
                        if final_translation.startswith("[TRANSLATION_FAILED") or not self._is_likely_translated(original_chunk, final_translation, source_lang, target_lang):
                            logger.translation_logger.warning(f"Cached stage 2 chunk {i} appears untranslated, re-translating...")
                            if VERBOSE_DEBUG:
                                debug_print(f"   ⚠️ Cache invalid, re-improving...", 'WARNING', 'TRANS')
                            cached_result = None  # Force re-translation
                        else:
                            logger.translation_logger.info(f"Cache hit for stage 2 chunk {i}")
                            if VERBOSE_DEBUG:
                                debug_print(f"   💾 Cache HIT", 'INFO', 'TRANS')
                    
                    if not cached_result:
                        logger.translation_logger.info(f"Stage 2 improving chunk {i}/{total_chunks}")
                        if VERBOSE_DEBUG:
                            debug_print(f"   🔄 Improving...", 'INFO', 'TRANS')
                        
                        final_translation = self.stage2_reflection_improvement(
                            original_text=original_chunk,
                            draft_translation=draft_chunk,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            previous_chunk=previous_final,
                            genre=genre
                        )
                        
                        if VERBOSE_DEBUG:
                            debug_print(f"   ✅ Improvement done!", 'INFO', 'TRANS')
                        
                        # Check if translation failed
                        if final_translation.startswith("[TRANSLATION_FAILED"):
                            # Use draft translation as fallback if it's valid
                            if draft_chunk and not draft_chunk.startswith("[TRANSLATION_FAILED") and \
                               self._is_likely_translated(original_chunk, draft_chunk, source_lang, target_lang):
                                logger.translation_logger.warning(f"Stage 2 chunk {i} failed, using draft")
                                final_translation = draft_chunk
                            else:
                                error_msg = f"Chunk {i} translation completely failed"
                                logger.translation_logger.error(error_msg)
                                raise Exception(error_msg)
                        
                        # Clean the response to avoid duplicates
                        final_translation = self._clean_translation_response(final_translation, previous_final)
                        
                        # Only cache if translation was successful
                        if self._is_likely_translated(original_chunk, final_translation, source_lang, target_lang):
                            cache.cache_translation(
                                original_chunk, final_translation, draft_chunk,
                                source_lang, target_lang, self.model_name + "_stage2", context_hash
                            )
                        time.sleep(0.5)
                    
                    final_translations.append(final_translation)
                    
                    progress = ((i + total_chunks) / (total_chunks * 2)) * 100
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute('''
                            UPDATE translations 
                            SET progress = ?,
                                translated_text = ?,
                                machine_translation = ?,
                                current_chunk = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (
                            progress,
                            '\n\n'.join(final_translations),
                            '\n\n'.join(draft_translations),
                            i + total_chunks,
                            translation_id
                        ))
                        
                    yield {
                        'progress': progress,
                        'stage': 'reflection_improvement',
                        'original_text': '\n\n'.join(chunks),
                        'machine_translation': '\n\n'.join(draft_translations),
                        'translated_text': '\n\n'.join(final_translations),
                        'current_chunk': i + total_chunks,
                        'total_chunks': total_chunks * 2
                    }
                    
                except Exception as e:
                    error_msg = f"Error in stage 2 chunk {i}: {str(e)}"
                    logger.translation_logger.error(error_msg)
                    logger.translation_logger.error(traceback.format_exc())
                    # Fallback to draft if it's valid, otherwise skip
                    if draft_chunk and not draft_chunk.startswith("[TRANSLATION_FAILED") and \
                       self._is_likely_translated(original_chunk, draft_chunk, source_lang, target_lang):
                        final_translations.append(draft_chunk)
                    else:
                        logger.translation_logger.error(f"No valid translation for chunk {i}, marking as failed")
                        final_translations.append(f"[⚠️ TRANSLATION FAILED - Chunk {i}]")
                
            # Post-process: Remove any duplicate paragraphs in the final result
            final_text = '\n\n'.join(final_translations)
            
            if VERBOSE_DEBUG:
                debug_print(f"\n▶ POST-PROCESSING", 'INFO', 'TRANS')
                debug_print(f"{'─'*40}", 'INFO', 'TRANS')
                debug_print(f"   Removing duplicate paragraphs...", 'INFO', 'TRANS')
            
            final_text = self._remove_duplicate_paragraphs(final_text)
            
            # Detect and mark any untranslated content
            if VERBOSE_DEBUG:
                debug_print(f"   Detecting untranslated content...", 'INFO', 'TRANS')
            
            final_text, untranslated = self._detect_untranslated_content(final_text, source_lang, target_lang)
            if untranslated:
                logger.translation_logger.warning(f"Found {len(untranslated)} possibly untranslated paragraphs")
                if VERBOSE_DEBUG:
                    debug_print(f"   ⚠️ Found {len(untranslated)} possibly untranslated paragraphs", 'WARNING', 'TRANS')
            
            draft_text = '\n\n'.join(draft_translations)
            
            # Mark translation as completed
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    UPDATE translations 
                    SET status = 'completed',
                        progress = 100,
                        translated_text = ?,
                        machine_translation = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (final_text, draft_text, translation_id))
                
            success = True
            
            # VERBOSE DEBUG: Print completion banner
            if VERBOSE_DEBUG:
                elapsed = time.time() - start_time
                debug_print(f"\n{'='*60}", 'INFO', 'TRANS')
                debug_print(f"✅ TRANSLATION COMPLETED!", 'INFO', 'TRANS')
                debug_print(f"{'='*60}", 'INFO', 'TRANS')
                debug_print(f"  ⏱️  Time: {elapsed:.1f} seconds", 'INFO', 'TRANS')
                debug_print(f"  📄 Final text: {len(final_text)} characters", 'INFO', 'TRANS')
                debug_print(f"  🔢 Chunks processed: {total_chunks}", 'INFO', 'TRANS')
                if untranslated:
                    debug_print(f"  ⚠️  Warnings: {len(untranslated)} possibly untranslated sections", 'WARNING', 'TRANS')
                debug_print(f"{'='*60}\n", 'INFO', 'TRANS')
            
            yield {
                'progress': 100,
                'original_text': '\n\n'.join(chunks),
                'machine_translation': draft_text,
                'translated_text': final_text,
                'status': 'completed',
                'warnings': f'{len(untranslated)} possibly untranslated sections' if untranslated else None
            }
            
        except Exception as e:
            error_msg = f"Translation failed: {str(e)}"
            logger.translation_logger.error(error_msg)
            logger.translation_logger.error(traceback.format_exc())
            
            # VERBOSE DEBUG: Print error banner
            if VERBOSE_DEBUG:
                debug_print(f"\n{'='*60}", 'ERROR', 'TRANS')
                debug_print(f"❌ TRANSLATION FAILED!", 'ERROR', 'TRANS')
                debug_print(f"{'='*60}", 'ERROR', 'TRANS')
                debug_print(f"  Error: {str(e)}", 'ERROR', 'TRANS')
                debug_print(f"{'='*60}\n", 'ERROR', 'TRANS')
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    UPDATE translations 
                    SET status = 'error',
                        error_message = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (str(e), translation_id))
            raise
        finally:
            translation_time = time.time() - start_time
            monitor.record_translation_attempt(success, translation_time)
            
    def stage1_primary_translation(self, text: str, source_lang: str, target_lang: str, 
                                   previous_chunk: str = "", genre: str = "unknown") -> str:
        """
        STAGE 1: Primary translation with maximum context.
        LLM translates with understanding of topic, audience, and style.
        """
        # Language names
        lang_names = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'zh': 'Chinese',
            'ja': 'Japanese', 'ko': 'Korean'
        }
        
        source_name = lang_names.get(source_lang, source_lang)
        target_name = lang_names.get(target_lang, target_lang)
        
        # Context section - show last 200 chars max to provide continuity without confusion
        context_section = ""
        if previous_chunk:
            prev_snippet = previous_chunk[-300:] if len(previous_chunk) > 300 else previous_chunk
            context_section = f"\n\n[For continuity only - the previous section ended with:]\n...{prev_snippet}"
        
        # Build prompt with explicit instructions to avoid duplication
        prompt = f"""You are a professional translator. Translate from {source_name} to {target_name}.

CRITICAL INSTRUCTIONS:
- Translate ONLY the text in "TEXT TO TRANSLATE" section below
- DO NOT repeat or include any text from the "previous section" context
- DO NOT add any prefix, suffix, or commentary
- Preserve formatting (paragraphs, line breaks)
- Adapt idioms and cultural references for target audience
- Maintain tone and emotional coloring of original
- Document type: {genre}
{context_section}

TEXT TO TRANSLATE:
{text}

IMPORTANT: Return ONLY the translation of the above text. Do not repeat previous content."""

        # VERBOSE DEBUG: Log full prompt
        if VERBOSE_DEBUG:
            logger.api_logger.debug(f"\n{'='*50}")
            logger.api_logger.debug(f"📝 STAGE 1 PROMPT ({len(prompt)} chars):")
            logger.api_logger.debug(f"{'='*50}")
            # Show first 500 and last 300 chars of prompt
            if len(prompt) > 900:
                logger.api_logger.debug(f"{prompt[:500]}\n...\n[{len(prompt)-800} chars omitted]\n...\n{prompt[-300:]}")
            else:
                logger.api_logger.debug(prompt)
            logger.api_logger.debug(f"{'='*50}")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.6}
        }
        
        # Retry logic for failed translations
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.api_logger.debug(f"🚀 Stage 1 - Sending request to {self.api_url} (attempt {attempt+1}/{max_retries})")
                logger.api_logger.debug(f"   Model: {self.model_name}, Temperature: 0.6")
                
                response = self.session.post(self.api_url, json=payload, timeout=(30, 300))  # 5 min timeout
                response.raise_for_status()
                result = json.loads(response.text)
                
                if 'response' in result:
                    translated = result['response'].strip()
                    
                    # VERBOSE DEBUG: Log translation result
                    if VERBOSE_DEBUG:
                        logger.api_logger.debug(f"✅ Stage 1 - Received response ({len(translated)} chars)")
                        logger.api_logger.debug(f"   First 200 chars: {translated[:200]}...")
                    
                    # Verify that the response is actually translated (not just the original)
                    if self._is_likely_translated(text, translated, source_lang, target_lang):
                        logger.api_logger.info(f"✅ Stage 1 SUCCESS - Translation validated")
                        return translated
                    else:
                        logger.api_logger.warning(f"⚠️ Stage 1 attempt {attempt+1}: Response seems untranslated, retrying...")
                        logger.api_logger.debug(f"   Rejected translation: {translated[:100]}...")
                        last_error = "Response appears to be untranslated"
                        continue
                        
                logger.api_logger.warning(f"No response field in Stage 1 result, attempt {attempt+1}")
                last_error = "No response field"
                
            except requests.exceptions.Timeout:
                logger.api_logger.error(f"Stage 1 timeout attempt {attempt+1}/{max_retries}")
                last_error = "Timeout"
                time.sleep(2)  # Wait before retry
            except Exception as e:
                logger.api_logger.error(f"Stage 1 error attempt {attempt+1}: {e}")
                last_error = str(e)
                time.sleep(1)
        
        # All retries failed - log error and mark as needing attention
        logger.api_logger.error(f"Stage 1 FAILED after {max_retries} attempts: {last_error}")
        # Return a marker that indicates translation failed (will be caught later)
        return f"[TRANSLATION_FAILED: {text[:100]}...]"
    
    def stage2_reflection_improvement(self, original_text: str, draft_translation: str,
                                     source_lang: str, target_lang: str,
                                     previous_chunk: str = "", genre: str = "unknown") -> str:
        """
        STAGE 2: Reflection and improvement.
        LLM critiques its own work and produces polished final version.
        """
        # Language names
        lang_names = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'zh': 'Chinese',
            'ja': 'Japanese', 'ko': 'Korean'
        }
        
        source_name = lang_names.get(source_lang, source_lang)
        target_name = lang_names.get(target_lang, target_lang)
        
        # Context section - show last 200 chars max for continuity reference
        context_section = ""
        if previous_chunk:
            prev_snippet = previous_chunk[-300:] if len(previous_chunk) > 300 else previous_chunk
            context_section = f"\n\n[For style continuity only - previous section ended:]\n...{prev_snippet}"
        
        # Build prompt with explicit instructions to avoid duplication
        prompt = f"""You are a translation editor. Improve this translation.

CRITICAL INSTRUCTIONS:
- Improve ONLY the "DRAFT TRANSLATION" below
- DO NOT repeat or include text from the "previous section" context
- DO NOT add any prefix, suffix, explanation, or commentary
- Return ONLY the improved translation text

ORIGINAL TEXT ({source_name}):
{original_text}

DRAFT TRANSLATION TO IMPROVE ({target_name}):
{draft_translation}
{context_section}

EVALUATION CRITERIA:
1. ACCURACY - Is all meaning preserved?
2. NATURALNESS - Does it sound native?
3. STYLE & TONE - Is the register maintained?
4. CULTURAL ADAPTATION - Are idioms adapted?

IMPORTANT: Return ONLY the improved translation. Nothing else."""

        # VERBOSE DEBUG: Log full prompt
        if VERBOSE_DEBUG:
            logger.api_logger.debug(f"\n{'='*50}")
            logger.api_logger.debug(f"📝 STAGE 2 PROMPT ({len(prompt)} chars):")
            logger.api_logger.debug(f"{'='*50}")
            # Show first 500 and last 300 chars of prompt
            if len(prompt) > 900:
                logger.api_logger.debug(f"{prompt[:500]}\n...\n[{len(prompt)-800} chars omitted]\n...\n{prompt[-300:]}")
            else:
                logger.api_logger.debug(prompt)
            logger.api_logger.debug(f"{'='*50}")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4}  # Lower for precision
        }
        
        # Retry logic for failed translations
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.api_logger.debug(f"🚀 Stage 2 - Sending request to {self.api_url} (attempt {attempt+1}/{max_retries})")
                logger.api_logger.debug(f"   Model: {self.model_name}, Temperature: 0.4")
                
                response = self.session.post(self.api_url, json=payload, timeout=(30, 300))  # 5 min timeout
                response.raise_for_status()
                result = json.loads(response.text)
                
                if 'response' in result:
                    translated = result['response'].strip()
                    
                    # VERBOSE DEBUG: Log translation result
                    if VERBOSE_DEBUG:
                        logger.api_logger.debug(f"✅ Stage 2 - Received response ({len(translated)} chars)")
                        logger.api_logger.debug(f"   First 200 chars: {translated[:200]}...")
                    
                    # Verify that the response is actually translated
                    if self._is_likely_translated(original_text, translated, source_lang, target_lang):
                        logger.api_logger.info(f"✅ Stage 2 SUCCESS - Translation validated")
                        return translated
                    else:
                        logger.api_logger.warning(f"⚠️ Stage 2 attempt {attempt+1}: Response seems untranslated, retrying...")
                        logger.api_logger.debug(f"   Rejected translation: {translated[:100]}...")
                        last_error = "Response appears to be untranslated"
                        continue
                        
                logger.api_logger.warning(f"No response field in Stage 2 result, attempt {attempt+1}")
                last_error = "No response field"
                
            except requests.exceptions.Timeout:
                logger.api_logger.error(f"Stage 2 timeout attempt {attempt+1}/{max_retries}")
                last_error = "Timeout"
                time.sleep(2)
            except Exception as e:
                logger.api_logger.error(f"Stage 2 error attempt {attempt+1}: {e}")
                last_error = str(e)
                time.sleep(1)
        
        # All retries failed - use draft translation if it looks translated, otherwise mark as failed
        if draft_translation and not draft_translation.startswith("[TRANSLATION_FAILED"):
            if self._is_likely_translated(original_text, draft_translation, source_lang, target_lang):
                logger.api_logger.warning("Stage 2 failed, using draft translation as fallback")
                return draft_translation
        
        logger.api_logger.error(f"Stage 2 FAILED after {max_retries} attempts: {last_error}")
        return f"[TRANSLATION_FAILED: {original_text[:100]}...]"
    
    def get_available_models(self) -> List[str]:
        response = self.session.get(
            "http://localhost:11434/api/tags",
            timeout=(5, 5)
        )
        response.raise_for_status()
        models = response.json()
        return [model['name'] for model in models['models']]
    
# Translation Recovery
class TranslationRecovery:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        
    def get_failed_translations(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('''
                SELECT * FROM translations 
                WHERE status = 'error'
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cur.fetchall()]
        
    def retry_translation(self, translation_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE translations
                SET status = 'pending', progress = 0, error_message = NULL,
                    current_chunk = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (translation_id,))
            
            conn.execute('''
                UPDATE chunks
                SET status = 'pending', error_message = NULL
                WHERE translation_id = ? AND status = 'error'
            ''', (translation_id,))
            
    def cleanup_failed_translations(self, days: int = 7):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"DELETE FROM translations WHERE status = 'error' AND created_at < datetime('now', '-{days} days')"
            )
            
recovery = TranslationRecovery()

# Health checking middleware
@app.before_request
def check_ollama():
    if request.endpoint != 'health_check':
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.app_logger.error(f"Ollama health check failed: {str(e)}")
            return jsonify({
                'error': 'Translation service is not available'
            }), 503
        
# Flask routes
@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get logs from in-memory buffer for the frontend console panel"""
    since_id = request.args.get('since', 0, type=int)
    if since_id > 0:
        logs = log_buffer.get_since(since_id)
    else:
        logs = log_buffer.get_all()
    return jsonify({'logs': logs})

@app.route('/logs/stream')
def stream_logs():
    """Stream logs in real-time using Server-Sent Events"""
    def generate():
        last_id = 0
        while True:
            logs = log_buffer.get_since(last_id)
            for log in logs:
                last_id = log['id']
                yield f"data: {json.dumps(log)}\n\n"
            time.sleep(0.5)  # Poll every 500ms
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/models', methods=['GET'])
@with_error_handling
def get_models():
    translator = BookTranslator()
    available_models = translator.get_available_models()
    models = []
    for model_name in available_models:
        models.append({
            'name': model_name,
            'size': 'Unknown',
            'modified': 'Unknown'
        })
    return jsonify({'models': models})

@app.route('/translations', methods=['GET'])
@with_error_handling
def get_translations():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute('''
            SELECT id, filename, source_lang, target_lang, model,
                   status, progress, detected_language, created_at, 
                   updated_at, error_message
            FROM translations
            ORDER BY created_at DESC
        ''')
        translations = [dict(row) for row in cur.fetchall()]
    return jsonify({'translations': translations})

@app.route('/translations/<int:translation_id>', methods=['GET'])
@with_error_handling
def get_translation(translation_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute('SELECT * FROM translations WHERE id = ?', (translation_id,))
        translation = cur.fetchone()
        if translation:
            return jsonify(dict(translation))
        return jsonify({'error': 'Translation not found'}), 404
    
@app.route('/translate', methods=['POST'])
@with_error_handling
def translate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    try:
        file = request.files['file']
        source_lang = request.form.get('sourceLanguage')
        target_lang = request.form.get('targetLanguage')
        model_name = request.form.get('model')
        genre = request.form.get('genre', 'unknown')  # Get genre from request
        
        if not all([file, source_lang, target_lang, model_name]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='cp1251') as f:
                text = f.read()
                
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute('''
                INSERT INTO translations (
                    filename, source_lang, target_lang, model,
                    status, original_text, genre
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (filename, source_lang, target_lang, model_name, 
                  'in_progress', text, genre))
            translation_id = cur.lastrowid
            
        translator = BookTranslator(model_name=model_name)
        
        def generate():
            try:
                for update in translator.translate_text(text, source_lang, target_lang, translation_id, genre=genre):
                    yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_message = str(e)
                logger.translation_logger.error(f"Translation error: {error_message}")
                logger.translation_logger.error(traceback.format_exc())
                yield f"data: {json.dumps({'error': error_message})}\n\n"
                
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        logger.app_logger.error(f"Translation request error: {str(e)}")
        logger.app_logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            if 'filepath' in locals():
                os.remove(filepath)
        except Exception as e:
            logger.app_logger.error(f"Failed to cleanup uploaded file: {str(e)}")
            
@app.route('/download/<int:translation_id>', methods=['GET'])
@with_error_handling
def download_translation(translation_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute('''
            SELECT filename, translated_text
            FROM translations
            WHERE id = ? AND status = 'completed'
        ''', (translation_id,))
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Translation not found or not completed'}), 404
        
        filename, translated_text = result
        
        download_path = os.path.join(TRANSLATIONS_FOLDER, f'translated_{filename}')
        with open(download_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
            
        return send_file(
            download_path,
            as_attachment=True,
            download_name=f'translated_{filename}'
        )
    
@app.route('/export/epub', methods=['POST'])
@with_error_handling
def export_epub():
    """Export translation as EPUB file"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        title = data.get('title', 'Translation')
        author = data.get('author', 'Book Translator')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Create unique filename
        epub_id = str(uuid.uuid4())
        epub_filename = f'translation_{epub_id}.epub'
        epub_path = os.path.join(TRANSLATIONS_FOLDER, epub_filename)
        
        # Create EPUB structure
        with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as epub:
            # mimetype (must be first, uncompressed)
            epub.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            
            # META-INF/container.xml
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            epub.writestr('META-INF/container.xml', container_xml)
            
            # OEBPS/content.opf
            content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookID">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{title}</dc:title>
        <dc:creator>{author}</dc:creator>
        <dc:language>en</dc:language>
        <dc:identifier id="BookID">{epub_id}</dc:identifier>
        <meta property="dcterms:modified">{dt.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    </manifest>
    <spine toc="ncx">
        <itemref idref="chapter1"/>
    </spine>
</package>'''
            epub.writestr('OEBPS/content.opf', content_opf)
            
            # OEBPS/toc.ncx
            toc_ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{epub_id}"/>
        <meta name="dtb:depth" content="1"/>
    </head>
    <docTitle>
        <text>{title}</text>
    </docTitle>
    <navMap>
        <navPoint id="chapter1" playOrder="1">
            <navLabel>
                <text>Chapter 1</text>
            </navLabel>
            <content src="chapter1.xhtml"/>
        </navPoint>
    </navMap>
</ncx>'''
            epub.writestr('OEBPS/toc.ncx', toc_ncx)
            
            # OEBPS/chapter1.xhtml
            # Convert paragraphs to HTML
            paragraphs = text.split('\n\n')
            html_paragraphs = ''.join([f'<p>{p.strip()}</p>\n' for p in paragraphs if p.strip()])
            
            chapter_xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: serif; line-height: 1.6; margin: 2em; }}
        p {{ margin-bottom: 1em; text-indent: 1.5em; }}
        p:first-of-type {{ text-indent: 0; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {html_paragraphs}
</body>
</html>'''
            epub.writestr('OEBPS/chapter1.xhtml', chapter_xhtml)
        
        logger.app_logger.info(f"EPUB created: {epub_filename}")
        
        return send_file(
            epub_path,
            as_attachment=True,
            download_name=f'{title.replace(" ", "_")}.epub',
            mimetype='application/epub+zip'
        )
        
    except Exception as e:
        logger.app_logger.error(f"EPUB export error: {str(e)}")
        logger.app_logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/failed-translations', methods=['GET'])
@with_error_handling
def get_failed_translations():
    return jsonify(recovery.get_failed_translations())

@app.route('/retry-translation/<int:translation_id>', methods=['POST'])
@with_error_handling
def retry_failed_translation(translation_id):
    recovery.retry_translation(translation_id)
    return jsonify({'status': 'success'})

@app.route('/clear-cache', methods=['POST'])
@with_error_handling
def clear_cache():
    """Clear the translation cache. Useful after fixing bugs or for testing."""
    cache.clear_all()
    return jsonify({'status': 'success', 'message': 'Translation cache cleared'})

@app.route('/metrics', methods=['GET'])
def get_metrics():
    return jsonify(monitor.get_metrics())

@app.route('/health', methods=['GET'])
def health_check():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('SELECT 1')
            
        disk_usage = psutil.disk_usage('/')
        if disk_usage.percent > 90:
            logger.app_logger.warning("Low disk space")
            
        return jsonify({
            'status': 'healthy',
            'ollama': 'connected',
            'database': 'connected',
            'disk_usage': f"{disk_usage.percent}%"
        })
    except Exception as e:
        logger.app_logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
    
def cleanup_old_data():
    while True:
        try:
            logger.app_logger.info("Running cleanup task")
            try:
                cache.cleanup_old_entries()
                logger.app_logger.info("Cache cleanup completed")
            except Exception as e:
                logger.app_logger.error(f"Cache cleanup error: {str(e)}")
                
            try:
                recovery.cleanup_failed_translations()
                logger.app_logger.info("Failed translations cleanup completed")
            except Exception as e:
                logger.app_logger.error(f"Failed translations cleanup error: {str(e)}")
                
            time.sleep(24 * 60 * 60)  # Run daily
        except Exception as e:
            logger.app_logger.error(f"Cleanup task error: {str(e)}")
            time.sleep(60 * 60)  # Retry in an hour
            
# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_data, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("Shutting down gracefully...")
        # Cleanup any running translations
        try:
            if 'translator' in locals():
                translator.cleanup()
        except Exception as e:
            logger.app_logger.error(f"Cleanup error during shutdown: {str(e)}")
            
        # Stop the cleanup thread
        if 'cleanup_thread' in globals() and cleanup_thread.is_alive():
            try:
                # Signal the cleanup thread to stop
                cleanup_thread._stop()
            except Exception as e:
                logger.app_logger.error(f"Error stopping cleanup thread: {str(e)}")
                
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=5001, debug=True)