"""
Constants and Enums for Book Translator
"""
from enum import Enum, auto
from typing import Dict, List, Any

# Supported languages with their display names
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish', 
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
}


class TranslationStatus(str, Enum):
    """Status of a translation job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TranslationStage(str, Enum):
    """Stages of the two-stage translation."""
    PRIMARY = "primary_translation"
    REFLECTION = "reflection_improvement"


# Comprehensive language markers for detection
LANGUAGE_MARKERS: Dict[str, Dict[str, Any]] = {
    'en': {
        'type': 'word',
        'markers': [
            ' the ', ' a ', ' an ', ' this ', ' that ', ' these ', ' those ',
            ' some ', ' any ', ' no ', ' every ', ' each ', ' all ', ' both ',
            ' i ', ' you ', ' he ', ' she ', ' it ', ' we ', ' they ',
            ' me ', ' him ', ' her ', ' us ', ' them ', ' my ', ' your ',
            ' his ', ' its ', ' our ', ' their ', ' mine ', ' yours ',
            ' who ', ' whom ', ' whose ', ' which ', ' what ',
            ' is ', ' are ', ' was ', ' were ', ' be ', ' been ', ' being ',
            ' have ', ' has ', ' had ', ' having ', ' do ', ' does ', ' did ',
            ' will ', ' would ', ' shall ', ' should ', ' can ', ' could ',
            ' may ', ' might ', ' must ', ' need ', ' dare ', ' ought ',
            ' said ', ' says ', ' told ', ' asked ', ' answered ', ' replied ',
            ' went ', ' came ', ' got ', ' made ', ' took ', ' gave ', ' knew ',
            ' thought ', ' felt ', ' saw ', ' heard ', ' seemed ', ' looked ',
            ' in ', ' on ', ' at ', ' by ', ' for ', ' with ', ' about ',
            ' against ', ' between ', ' into ', ' through ', ' during ',
            ' before ', ' after ', ' above ', ' below ', ' from ', ' up ',
            ' down ', ' out ', ' off ', ' over ', ' under ', ' again ',
            ' and ', ' but ', ' or ', ' nor ', ' so ', ' yet ', ' because ',
            ' although ', ' while ', ' if ', ' unless ', ' until ', ' when ',
            ' where ', ' whether ', ' however ', ' therefore ', ' moreover ',
            ' not ', ' very ', ' really ', ' just ', ' also ', ' only ',
            ' even ', ' still ', ' already ', ' always ', ' never ', ' often ',
            ' sometimes ', ' usually ', ' here ', ' there ', ' now ', ' then ',
            ' of the ', ' to the ', ' in the ', ' on the ', ' at the ',
            ' and the ', ' for the ', ' with the ', ' from the ',
            ' there is ', ' there are ', ' there was ', ' there were ',
        ],
        'min_markers': 3,
    },
    'es': {
        'type': 'word',
        'markers': [
            ' el ', ' la ', ' los ', ' las ', ' un ', ' una ', ' unos ', ' unas ',
            ' de ', ' del ', ' al ', ' en ', ' con ', ' por ', ' para ', ' sin ',
            ' sobre ', ' entre ', ' hacia ', ' desde ', ' hasta ', ' según ',
            ' durante ', ' mediante ', ' contra ', ' ante ', ' bajo ',
            ' yo ', ' tú ', ' él ', ' ella ', ' usted ', ' nosotros ', ' ellos ',
            ' ellas ', ' ustedes ', ' me ', ' te ', ' le ', ' nos ', ' les ',
            ' lo ', ' se ', ' mi ', ' tu ', ' su ', ' mis ', ' tus ', ' sus ',
            ' que ', ' quien ', ' cual ', ' cuyo ', ' donde ', ' como ', ' cuando ',
            ' es ', ' son ', ' era ', ' eran ', ' fue ', ' fueron ', ' ser ', ' sido ',
            ' está ', ' están ', ' estaba ', ' estuvo ', ' estar ', ' estado ',
            ' ha ', ' han ', ' había ', ' hubo ', ' haber ', ' habido ',
            ' tiene ', ' tienen ', ' tenía ', ' tuvo ', ' tener ', ' tenido ',
            ' y ', ' e ', ' o ', ' u ', ' pero ', ' sino ', ' aunque ', ' porque ',
            ' no ', ' sí ', ' muy ', ' más ', ' menos ', ' bien ', ' mal ',
            ' de la ', ' de los ', ' de las ', ' en el ', ' en la ',
        ],
        'min_markers': 3,
    },
    'fr': {
        'type': 'word',
        'markers': [
            ' le ', ' la ', ' les ', ' un ', ' une ', ' des ', ' du ', ' de la ',
            " l'", " d'", " n'", " s'", " c'", " j'", " m'", " t'", " qu'",
            ' de ', ' à ', ' en ', ' dans ', ' sur ', ' sous ', ' avec ', ' sans ',
            ' pour ', ' par ', ' chez ', ' vers ', ' entre ', ' contre ',
            ' je ', ' tu ', ' il ', ' elle ', ' on ', ' nous ', ' vous ', ' ils ', ' elles ',
            ' est ', ' sont ', ' était ', ' étaient ', ' fut ', ' être ', ' été ',
            ' a ', ' ont ', ' avait ', ' avaient ', ' eut ', ' avoir ', ' eu ',
            ' et ', ' ou ', ' mais ', ' donc ', ' car ', ' ni ', ' or ',
            ' ne ', ' pas ', ' plus ', ' jamais ', ' rien ', ' personne ',
            " c'est ", " c'était ", " il y a ", " il y avait ",
        ],
        'min_markers': 3,
    },
    'de': {
        'type': 'word',
        'markers': [
            ' der ', ' die ', ' das ', ' den ', ' dem ', ' des ',
            ' ein ', ' eine ', ' einen ', ' einem ', ' einer ', ' eines ',
            ' in ', ' an ', ' auf ', ' für ', ' mit ', ' von ', ' zu ', ' bei ',
            ' ich ', ' du ', ' er ', ' sie ', ' es ', ' wir ', ' ihr ',
            ' ist ', ' sind ', ' war ', ' waren ', ' sein ', ' gewesen ',
            ' hat ', ' haben ', ' hatte ', ' hatten ', ' gehabt ',
            ' und ', ' oder ', ' aber ', ' denn ', ' weil ', ' dass ', ' daß ',
            ' nicht ', ' auch ', ' nur ', ' noch ', ' schon ', ' sehr ',
        ],
        'min_markers': 3,
    },
    'it': {
        'type': 'word',
        'markers': [
            ' il ', ' lo ', ' la ', ' i ', ' gli ', ' le ',
            ' un ', ' uno ', ' una ', " un'", ' del ', ' dello ', ' della ',
            " l'", " d'", " c'", " n'", " s'",
            ' di ', ' a ', ' da ', ' in ', ' con ', ' su ', ' per ', ' tra ', ' fra ',
            ' io ', ' tu ', ' lui ', ' lei ', ' noi ', ' voi ', ' loro ',
            ' è ', ' sono ', ' era ', ' erano ', ' fu ', ' furono ', ' essere ', ' stato ',
            ' e ', ' o ', ' ma ', ' però ', ' perché ', ' poiché ', ' quando ',
            ' non ', ' sì ', ' molto ', ' poco ', ' più ', ' meno ', ' bene ', ' male ',
        ],
        'min_markers': 3,
    },
    'pt': {
        'type': 'word',
        'markers': [
            ' o ', ' a ', ' os ', ' as ', ' um ', ' uma ', ' uns ', ' umas ',
            ' do ', ' da ', ' dos ', ' das ', ' no ', ' na ', ' nos ', ' nas ',
            ' de ', ' em ', ' com ', ' por ', ' para ', ' sem ', ' sob ', ' sobre ',
            ' eu ', ' tu ', ' ele ', ' ela ', ' você ', ' nós ', ' eles ', ' elas ',
            ' é ', ' são ', ' era ', ' eram ', ' foi ', ' foram ', ' ser ', ' sido ',
            ' e ', ' ou ', ' mas ', ' porém ', ' contudo ', ' todavia ', ' porque ',
            ' não ', ' sim ', ' muito ', ' pouco ', ' mais ', ' menos ', ' bem ', ' mal ',
        ],
        'min_markers': 3,
    },
    'ru': {
        'type': 'word',
        'markers': [
            ' в ', ' на ', ' с ', ' к ', ' у ', ' о ', ' за ', ' из ', ' по ', ' от ',
            ' я ', ' ты ', ' он ', ' она ', ' оно ', ' мы ', ' вы ', ' они ',
            ' это ', ' этот ', ' эта ', ' эти ', ' тот ', ' та ', ' те ',
            ' был ', ' была ', ' было ', ' были ', ' есть ', ' быть ', ' будет ',
            ' и ', ' а ', ' но ', ' или ', ' да ', ' ни ', ' же ', ' ли ',
            ' не ', ' ещё ', ' уже ', ' очень ', ' так ', ' как ', ' тоже ', ' также ',
        ],
        'min_markers': 3,
    },
    'zh': {
        'type': 'character',
        'markers': [
            '的', '了', '是', '在', '有', '和', '与', '或', '但', '而',
            '我', '你', '他', '她', '它', '们', '这', '那', '什么', '怎么',
            '不', '也', '都', '就', '还', '又', '才', '已', '很', '太',
            '着', '过', '地', '得', '吗', '呢', '吧', '啊', '呀', '哦',
            '如果', '虽然', '但是', '因为', '所以', '而且', '或者', '不过',
        ],
        'min_markers': 5,
    },
    'ja': {
        'type': 'character',
        'markers': [
            'の', 'は', 'が', 'を', 'に', 'で', 'と', 'も', 'や', 'か',
            'です', 'ます', 'でした', 'ました', 'である', 'ではない',
            'ない', 'なかった', 'ある', 'あった', 'いる', 'いた',
            'この', 'その', 'あの', 'どの', 'これ', 'それ', 'あれ', 'どれ',
            'という', 'として', 'について', 'によって', 'に対して',
        ],
        'min_markers': 5,
    },
    'ko': {
        'type': 'character',
        'markers': [
            '은', '는', '이', '가', '을', '를', '의', '에', '에서', '로',
            '이다', '입니다', '이에요', '예요', '였다', '였습니다',
            '하다', '합니다', '해요', '했다', '했습니다', '하는',
            '있다', '있습니다', '있어요', '없다', '없습니다', '없어요',
            '그리고', '그러나', '하지만', '그래서', '왜냐하면', '만약',
        ],
        'min_markers': 5,
    },
}
