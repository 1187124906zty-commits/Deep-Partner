import {describe,it,expect} from 'vitest'
import {academicMath} from './academicMath'
import katex from 'katex'

describe('academic mathematical typography',()=>{
 it('left aligns equation groups while retaining every operand and relation',()=>{
  const source=String.raw`\left\{\begin{matrix}h_0&=\phi(x),\\h_l&=\tanh(W_lh_{l-1}+b_l).\end{matrix}\right.`
  const shown=academicMath(source)
  expect(shown).toContain(String.raw`\begin{array}{l}`)
  expect(shown.replace(/\\def\\arraystretch\{[0-9.]+\}|^\{|\}$/g,'').replace(/\\(?:begin|end)\{(?:array|matrix)\}(?:\{[rl]\})?|\\displaystyle|&|\s+/g,'')).toBe(source.replace(/\\(?:begin|end)\{(?:array|matrix)\}(?:\{[rl]\})?|\\displaystyle|&|\s+/g,''))
  expect(()=>katex.renderToString(shown,{throwOnError:true})).not.toThrow()
 })
 it('left aligns both expressions and condition labels in a piecewise group',()=>{
  const shown=academicMath(String.raw`\left\{\begin{matrix}a,&\text{flux},\\b,&\text{humidity}.\end{matrix}\right.`)
  expect(shown).toContain(String.raw`\begin{array}{ll}`)
  expect(()=>katex.renderToString(shown,{throwOnError:true})).not.toThrow()
 })
 it('keeps numerical matrices and individual mathematical symbols intact',()=>{
  for(const source of [String.raw`\begin{bmatrix}x\\t\end{bmatrix}`,String.raw`\theta_H^{\ast}`,String.raw`\nabla\cdot[D(H)\nabla H]`])expect(academicMath(source)).toBe(source)
 })
 it('uses bold italic vector symbols without changing the variable',()=>{
  expect(academicMath(String.raw`\mathbf{\theta}_H`)).toBe(String.raw`\boldsymbol{\theta}_H`)
 })
 it('does not send invisible control characters to the math font renderer',()=>{
  expect(academicMath('H\u009d_1')).toBe('H_1')
 })
 it('uses upright descriptor subscripts and preserves algebraic indices',()=>{
  expect(academicMath(String.raw`H_{j}^{obs}+\mathcal{R}_{H,diff}`)).toBe(String.raw`H_{j}^{\mathrm{obs}}+\mathcal{R}_{H,\mathrm{diff}}`)
 })
 it('renders imported functions as mathematical operators and keeps normalization stable',()=>{
  const source=String.raw`\text{ln}H+\text{sin}(x)+\underset{\theta}{arg\, min}J+{RMSE}_{H}`
  const shown=academicMath(source)
  expect(shown).toContain(String.raw`\ln H`)
  expect(shown).toContain(String.raw`\operatorname{arg\,min}`)
  expect(academicMath(shown)).toBe(shown)
  expect(()=>katex.renderToString(shown,{throwOnError:true})).not.toThrow()
 })
})
