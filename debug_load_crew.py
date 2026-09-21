import runpy, sys, pathlib
p=pathlib.Path('c:/Users/LENOVO/Documents/AITesterBlueprint3x/chapter_12_CrewAI/01_Test_Analyst_Agent.py')
# ensure crewai stub directory on path
sys.path.insert(0, str(p.parent))
try:
    print('reading file:', p)
    text = p.read_text(encoding='utf-8')
    print('file length', len(text))
    print('first 200 chars:\n', text[:200])
    g = runpy.run_path(str(p))
    all_names = sorted(g.keys())
    print('all names in module:', all_names)
    names = sorted([k for k in g.keys() if k[0].islower()])
    print('defined lower-case names via run_path:', names)
    print('has crew?', 'crew' in g)
    print('crew repr:', repr(g.get('crew')))
except Exception as e:
    import traceback
    traceback.print_exc()
    print('exception during run_path', e)
