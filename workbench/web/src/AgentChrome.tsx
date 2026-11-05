import {Sparkles,X,ArrowUpRight,AlignLeft,Type,ScanText,GitCompareArrows} from 'lucide-react'
import {IconButton} from './ui'

export function AgentHeader({onClose,session}:{onClose?:()=>void;session?:string}){
 return <header className="context-agent-header"><span className="agent-emblem"><Sparkles size={15}/></span><div><strong>Agent</strong><small>当前工作区助手</small></div><div className="toolbar-spacer"/>{session&&<a title="打开完整会话" href={session} target="_blank" rel="noreferrer"><ArrowUpRight size={15}/></a>}{onClose&&<IconButton title="收起 Agent" onClick={onClose}><X size={16}/></IconButton>}</header>
}

export function AgentWelcome({area,onPrompt}:{area:string;onPrompt:(v:string)=>void}){
 const prompts=area==='image'?[['统一字体','统一这张图的字体、字号层次与图例样式，保持数据和单位。'],['对齐子图','检查并调整子图的对齐、间距和序号位置，保留各子图内容。'],['检查可读性','检查坐标轴、线条、图例和颜色的可读性，指出并修正具体问题。'],['追溯来源','说明当前图的绘图程序、数据来源和在论文中的使用位置。']]:area==='code'?[['解释代码','结合当前文件和选中行解释代码的作用、输入输出与调用关系。'],['定位错误','检查当前文件的错误，给出具体位置并修复，运行有意义的验证。'],['优化实现','简化当前实现并改善可读性，保留既有行为与科学计算含义。'],['关联结果','追溯当前程序使用的数据和产生的图表，指出相关文件路径。']]:[['优化选中内容','检查并优化选中内容的表达，保留原意、数值、公式与引用。'],['核对公式','核对选中公式的变量、单位和上下文，并指出需要补充的说明。'],['更新相关文献','检索与当前方法和研究对象相关的高质量文献，核验来源后提出引用建议。'],['检查排版','检查当前稿件的标题、公式编号、表格和图题排版，修正不一致之处。']]
 const icons=[Type,AlignLeft,ScanText,GitCompareArrows]
 return <div className="agent-welcome"><div className="agent-welcome-mark"><Sparkles size={23}/></div><h3>{area==='image'?'一起调整这张图':'从当前内容开始'}</h3><p>文件与选中内容已附在下方。直接描述修改要求，或从一个常用操作开始。</p><div className="agent-prompt-cards">{prompts.map(([title,prompt],i)=>{const Icon=icons[i];return <button key={title} onClick={()=>onPrompt(prompt)}><Icon size={15}/><span>{title}</span><ArrowUpRight size={12}/></button>})}</div></div>
}
