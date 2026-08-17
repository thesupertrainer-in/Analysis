import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import '@ui5/webcomponents-fiori/dist/ShellBar.js'
import '@ui5/webcomponents/dist/Button.js'
import '@ui5/webcomponents/dist/Card.js'
import '@ui5/webcomponents/dist/CardHeader.js'
import '@ui5/webcomponents/dist/Table.js'
import '@ui5/webcomponents/dist/TableHeaderRow.js'
import '@ui5/webcomponents/dist/TableHeaderCell.js'
import '@ui5/webcomponents/dist/TableRow.js'
import '@ui5/webcomponents/dist/TableCell.js'
import '@ui5/webcomponents/dist/Tag.js'
import '@ui5/webcomponents/dist/BusyIndicator.js'
import '@ui5/webcomponents/dist/MessageStrip.js'
import '@ui5/webcomponents/dist/FileUploader.js'
import '@ui5/webcomponents/dist/Label.js'
import '@ui5/webcomponents/dist/Title.js'
import '@ui5/webcomponents/dist/Icon.js'
import '@ui5/webcomponents-icons/dist/upload.js'
import '@ui5/webcomponents-icons/dist/download.js'
import '@ui5/webcomponents-icons/dist/play.js'
import '@ui5/webcomponents-icons/dist/history.js'
import '@ui5/webcomponents-icons/dist/status-positive.js'
import '@ui5/webcomponents-icons/dist/status-negative.js'
import '@ui5/webcomponents-icons/dist/status-in-process.js'
import '@ui5/webcomponents-icons/dist/warning.js'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
