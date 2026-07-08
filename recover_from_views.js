const fs = require('fs');
const path = require('path');

const brainDir = 'C:/Users/HP/.gemini/antigravity-ide/brain';

function getTranscriptFiles(dir) {
    let results = [];
    const list = fs.readdirSync(dir);
    list.forEach(file => {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);
        if (stat && stat.isDirectory()) {
            const logsDir = path.join(fullPath, '.system_generated', 'logs');
            if (fs.existsSync(logsDir)) {
                const transcriptFull = path.join(logsDir, 'transcript_full.jsonl');
                if (fs.existsSync(transcriptFull)) {
                    results.push(transcriptFull);
                }
            }
        }
    });
    return results;
}

const transcriptFiles = getTranscriptFiles(brainDir);

// We want to find viewed content of store.ts
// Specifically, step logs of type 'SYSTEM' or 'TOOL_OUTPUT' or similar that contains the file view response
for (const tFile of transcriptFiles) {
    const content = fs.readFileSync(tFile, 'utf8');
    const lines = content.split('\n');
    for (const line of lines) {
        if (!line.trim()) continue;
        if (line.toLowerCase().includes('store.ts') && line.includes('"status":"DONE"')) {
            try {
                const data = JSON.parse(line);
                // Check if this step is a tool execution result containing viewed content
                if (data.type === 'CODE_ACTION' || data.type === 'TOOL_OUTPUT' || data.content) {
                    if (data.content && data.content.includes('File Path:')) {
                        console.log(`Found viewed content in ${tFile} step ${data.step_index}`);
                        fs.appendFileSync('viewed_store_logs.txt', `--- STEP ${data.step_index} in ${tFile} ---\n${data.content}\n\n`);
                    }
                }
            } catch (e) {}
        }
    }
}
console.log('Search finished!');
