'use strict'
const config = require('conventional-changelog-conventionalcommits');

module.exports = config({
    "types": [
        { type: 'feat', section: '🎉 New Features' },
        { type: 'fix', section: '🐛 Bug Fixes' },
        { type: 'chore', section: '✍ Chore'},
        { type: 'ci', section: '🤖 CI/CD'},
        { type: 'cd', section: '🤖 CI/CD'},
        { type: 'style', section: '🔥 Style'},
        { type: 'docs', section: '📚 Documentation'},
        { type: 'test', section: '🧪 Tests'},
        { type: 'build', section: '🏭 Build'},
        { type: 'refactor', section: '📃 Refactor'}
    ]
})