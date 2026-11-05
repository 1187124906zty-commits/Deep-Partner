import React from 'react'
import {createRoot} from 'react-dom/client'
import App from './App'
import './style.css'
import 'katex/dist/katex.min.css'
import './tutor-theme.css'
import './tutor-ui.css'
import './figure-canvas.css'
import './workspace-refinement.css'
import './authoring.css'
import './dito-workspace.css'
import './figure-studio.css'
import {initializeTheme} from './theme'
initializeTheme()
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)

import './usability.css'
import './workbench-design.css'
