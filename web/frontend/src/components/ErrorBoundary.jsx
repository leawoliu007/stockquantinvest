import { Component } from 'react'

export class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary" style={{
          padding: 20,
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 8,
          margin: 20,
          color: '#f3f4f6',
        }}>
          <h3 style={{ color: '#ef4444', marginBottom: 8 }}>页面出错</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: '#9ca3af' }}>
            {this.state.error.message}
          </pre>
          <button onClick={() => this.setState({ error: null })} style={{
            marginTop: 12,
            padding: '6px 16px',
            background: '#ef4444',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
          }}>重试</button>
        </div>
      )
    }
    return this.props.children
  }
}
