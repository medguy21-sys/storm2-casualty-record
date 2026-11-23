from pathlib import Path
root=Path(__file__).resolve().parent
path=root/'index.html';text=path.read_text(encoding='utf-8');marker='<!-- VITAL_LAB_OPERATOR_BUNDLE -->'
prefix=text.split(marker,1)[0]
names=['display-template.js','policy.js','journey.js','operator-ui.js','camera-dock.js']
bundle='\n'.join((root/'src'/name).read_text(encoding='utf-8') for name in names)
path.write_text(prefix+marker+'\n<script>'+bundle+'</script></body></html>',encoding='utf-8')
print('Rebuilt self-contained Vital Lab index.html')
