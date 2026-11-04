with open('frontend/js/features/copilot/copilot-voice.js', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if '// Enviar para o chat do Copilot' in line:
        skip = True
        new_lines.append("    // Enviar diretamente para o assistente sem poluir o textarea de escrita manual\n")
        new_lines.append("    userEchoSeen = false;\n")
        new_lines.append("    if (typeof window.sendCopilotQuery === 'function') {\n")
        new_lines.append("      window.sendCopilotQuery(processed).then(success => {\n")
        new_lines.append("        if (!success) {\n")
        new_lines.append("          awaitingReply = false;\n")
        new_lines.append("          ignoreInput = false;\n")
        new_lines.append("          finalBuffer = processed;\n")
        new_lines.append("          _showText(processed);\n")
        new_lines.append("          _setOrbState('listening');\n")
        new_lines.append("          _setStatus('O Copilot ainda está a responder. Tente enviar de novo.');\n")
        new_lines.append("        }\n")
        new_lines.append("      });\n")
        new_lines.append("      userEchoSeen = true;\n")
        new_lines.append("    } else {\n")
        new_lines.append("      const input = document.getElementById('copilotUserInput');\n")
        new_lines.append("      const form  = document.getElementById('copilotInputForm');\n")
        new_lines.append("      if (input && form) {\n")
        new_lines.append("        input.value = processed;\n")
        new_lines.append("        form.dispatchEvent(new Event('submit', { cancelable: true }));\n")
        new_lines.append("      }\n")
        new_lines.append("    }\n")
    elif skip and 'if (!userEchoSeen) {' in line:
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open('frontend/js/features/copilot/copilot-voice.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Patch aplicado com sucesso!')

