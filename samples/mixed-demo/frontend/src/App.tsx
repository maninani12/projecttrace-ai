import React from 'react'
import { useState } from 'react'
export default function App() {
  const [description, setDescription] = useState('')
  async function submit() {
    await fetch('/api/complaints', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({description}) })
  }
  return <form onSubmit={event => { event.preventDefault(); void submit() }}><label>Complaint<input value={description} onChange={event => setDescription(event.target.value)}/></label><button>Submit</button></form>
}
