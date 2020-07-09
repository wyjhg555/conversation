import logging, re, aiohttp
from homeassistant.helpers import intent
import homeassistant.config as conf_util
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DOMAIN = "conversation"
DATA_AGENT = "conversation_agent"
DATA_CONFIG = "conversation_config"

def text_start(findText, text):
    return text.find(findText,0,len(findText)) >= 0

class Voice():

    def __init__(self, hass):
        self.hass = hass
        hass.services.async_register(DOMAIN, 'reload', self.reload)

    # 重新加载配置
    async def reload(self, service):
        hass = self.hass
        # 读取配置
        hass.data[DATA_CONFIG] = await conf_util.async_hass_config_yaml(hass)
        # 清除agent
        hass.data[DATA_AGENT] = None

    # 触发事件
    def fire_text(self, text):
        # 去掉前后标点符号
        _text = text.strip(' 。，、＇：∶；?‘’“”〝〞ˆˇ﹕︰﹔﹖﹑·¨….¸;！´？！～—ˉ｜‖＂〃｀@﹫¡¿﹏﹋﹌︴々﹟#﹩$﹠&﹪%*﹡﹢﹦﹤‐￣¯―﹨ˆ˜﹍﹎+=<­­＿_-\ˇ~﹉﹊（）〈〉‹›﹛﹜『』〖〗［］《》〔〕{}「」【】︵︷︿︹︽_﹁﹃︻︶︸﹀︺︾ˉ﹂﹄︼')    
        # 发送事件，共享给其他组件
        self.hass.bus.fire('ha_voice_text_event', {
            'text': _text
        })
        return _text

    # 执行自定义脚本
    async def execute_script(self, text):
        hass = self.hass
        states = hass.states.async_all()
        for state in states:
            entity_id = state.entity_id
            attributes = state.attributes
            state_value = state.state
            friendly_name = attributes.get('friendly_name')
            # 查询匹配脚本
            if entity_id.find('script.') == 0:
                cmd = friendly_name.split('=')
                if cmd.count(text) > 0:
                    arr = entity_id.split('.')
                    _LOGGER.info('执行脚本：' + entity_id)
                    await hass.services.async_call(arr[0], arr[1])
                    intent_result = intent.IntentResponse()
                    intent_result.async_set_speech("正在执行自定义脚本：" + entity_id)
                    return intent_result
            # 查询设备状态
            friendly_name_lower = friendly_name.lower()
            if text.lower() == friendly_name_lower + '的状态':
                intent_result = intent.IntentResponse()
                intent_result.async_set_speech(friendly_name + '的状态：' + state.state)
                return intent_result
            # 查询设备属性
            if text.lower() == friendly_name_lower + '的属性':
                tpl = template.Template('''
                {% set entity_id = "''' + entity_id + '''" -%}
                <table>
                    <tr>
                        <th>{{entity_id}}</th>
                        <th>{{states(entity_id)}}</th>
                    </tr>
                    {% for state in states[entity_id].attributes -%}
                    <tr>
                        <td>{{state}}</td>
                        <td>{{states[entity_id].attributes[state]}}</td>
                    </tr>  
                    {%- endfor %}
                </table>
                ''', hass)
                message = tpl.async_render(None)
                intent_result = intent.IntentResponse()
                intent_result.async_set_speech(message)
                return intent_result

        return None

    # 执行开关
    async def execute_switch(self, _text):
        hass = self.hass
        intent_type = ''
        if text_start('打开',_text) or text_start('开启',_text) or text_start('启动',_text):
            intent_type = 'HassTurnOn'
            if '打开' in _text:
                _name = _text.split('打开')[1]
            elif '开启' in _text:
                _name = _text.split('开启')[1]
            elif '启动' in _text:
                _name = _text.split('启动')[1]
        elif text_start('关闭',_text) or text_start('关掉',_text) or text_start('关上',_text):
            intent_type = 'HassTurnOff'
            if '关闭' in _text:
                _name = _text.split('关闭')[1]
            elif '关掉' in _text:
                _name = _text.split('关掉')[1]
            elif '关上' in _text:
                _name = _text.split('关上')[1]            
        elif text_start('切换', _text):
            intent_type = 'HassToggle'
            _name = _text.split('切换')[1]
        # 默认的开关操作
        if intent_type != '':
            # 操作所有灯和开关
            if _name == '所有灯' or _name == '所有的灯' or _name == '全部灯' or _name == '全部的灯':
                _name = 'all lights'
            elif _name == '所有开关' or _name == '所有的开关' or _name == '全部开关' or _name == '全部的开关':
                _name = 'all switchs'
            await intent.async_handle(hass, DOMAIN, intent_type, {'name': {'value': _name}})
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech("正在" + _text)
            return intent_result
        return None

    # 错误信息处理
    def error_msg(self, err_msg):
        # 没有找到设备
        if 'Unable to find an entity called' in err_msg:
            err_msg = err_msg.replace('Unable to find an entity called', '没有找到这个设备：')
        return err_msg

    # 聊天机器人
    async def chat_robot(self, text):
        message = "对不起，我不明白"
        try:
            async with aiohttp.request('GET','https://api.ownthink.com/bot?appid=xiaosi&spoken=' + text) as r:
                res = await r.json(content_type=None)
                _LOGGER.info(res)
                message = res['data']['info']['text']
        except Exception as e:
            _LOGGER.info(e)        
        return message
