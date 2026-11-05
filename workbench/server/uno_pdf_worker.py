"""Isolated Writer PDF rendering with explicit formula fonts and baselines.

Run with the runtime image's /usr/bin/python3 (python3-uno). The editable DOCX
is never rewritten by this renderer; OfficeMath remains in the delivered Word.
"""
from pathlib import Path
import argparse,json,subprocess,time,uuid
import uno
from word_math_render import prepare_math_styles,restore_math_styles
from com.sun.star.beans import PropertyValue


def prop(name,value):
    item=PropertyValue();item.Name=name;item.Value=value;return item


def main():
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('target');parser.add_argument('--profile',required=True);parser.add_argument('--font',required=True);parser.add_argument('--math-font');parser.add_argument('--script-percent',type=int);parser.add_argument('--cjk',default='SimSun');parser.add_argument('--size',type=float,required=True);args=parser.parse_args()
    math_font=args.math_font or args.font
    source=Path(args.source).resolve();target=Path(args.target).resolve();profile=Path(args.profile).resolve();pipe='workbench_'+uuid.uuid4().hex
    profile.mkdir(parents=True,exist_ok=True);styled_source=profile/'mathematical-styles.docx';styles=prepare_math_styles(source,styled_source)
    process=subprocess.Popen(['libreoffice','-env:UserInstallation='+profile.as_uri(),'--headless','--nologo','--norestore','--nodefault','--accept=pipe,name='+pipe+';urp;StarOffice.ComponentContext'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    desktop=document=None
    try:
        local=uno.getComponentContext();resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local);context=None
        for _ in range(100):
            try:context=resolver.resolve('uno:pipe,name='+pipe+';urp;StarOffice.ComponentContext');break
            except Exception:
                if process.poll() is not None:raise RuntimeError('Writer rendering process exited')
                time.sleep(.15)
        if context is None:raise RuntimeError('Writer rendering connection did not become ready')
        desktop=context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',context)
        document=desktop.loadComponentFromURL(styled_source.as_uri(),'_blank',0,(prop('Hidden',True),prop('ReadOnly',False),prop('UpdateDocMode',0),prop('MacroExecutionMode',uno.getConstantByName('com.sun.star.document.MacroExecMode.NEVER_EXECUTE'))))
        settings=document.createInstance('com.sun.star.text.DocumentSettings');settings.setPropertyValue('MathBaselineAlignment',True)
        embedded=document.getEmbeddedObjects();changed=0;sizes={};styles_restored=0
        for name in embedded.getElementNames():
            item=embedded.getByName(name);model=item.Model
            if not model.supportsService('com.sun.star.formula.FormulaProperties'):continue
            # Imported OMath anchor portions inherit Writer's 12 pt OLE default,
            # even when the surrounding Word run explicitly uses 10.5 pt.
            height=args.size
            # StarMath's document base size is an integer. Its size command keeps
            # the half-point sizes used in the source Word paragraph exactly.
            formula,restored=restore_math_styles(model.Formula,styles);styles_restored+=restored

            import re
            formula=re.sub(r'\bsize\s+\d+(?:\.\d+)?\s*(?![%\d.])','',formula)
            model.BaseFontHeight=round(height)
            for key,font in [('FontNameVariables',math_font),('FontNameFunctions',math_font),('FontNameNumbers',math_font),('FontNameText',args.cjk if args.cjk else math_font),('CustomFontNameSerif',math_font)]:
                model.setPropertyValue(key,font)
            model.FontVariablesIsItalic=True;model.FontFunctionsIsItalic=False;model.FontNumbersIsItalic=False;model.FontTextIsItalic=False
            if args.script_percent:
                model.RelativeFontHeightIndices=args.script_percent;model.RelativeFontHeightLimits=args.script_percent
            model.Alignment=0
            model.RelativeMatrixLineSpacing=25;model.RelativeLineSpacing=25
            model.Formula='size '+str(round(height,2))+' { '+formula+' }'
            # Resize the OLE frame to the formula's current visual size; keeping
            # the imported 12pt frame would scale the corrected glyphs back up.
            item.setSize(item.ExtendedControlOverEmbeddedObject.getVisualAreaSize(1))
            changed+=1;sizes[str(round(height,2))]=sizes.get(str(round(height,2)),0)+1
        if styles_restored!=len(styles):raise RuntimeError('Writer did not retain every explicit mathematical style')
        settings.setPropertyValue('MathBaselineAlignment',False)
        settings.setPropertyValue('MathBaselineAlignment',True)
        document.refresh()
        document.storeToURL(target.as_uri(),(prop('FilterName','writer_pdf_Export'),prop('Overwrite',True)))
        print(json.dumps({'formulas':changed,'math_baseline_alignment':True,'font':math_font,'body_font':args.font,'sizes':sizes,'source_docx_modified':False,'explicit_math_styles':styles_restored}),flush=True)
    finally:
        if document is not None:
            try:document.close(True)
            except Exception:pass
        if desktop is not None:
            try:desktop.terminate()
            except Exception:pass
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
