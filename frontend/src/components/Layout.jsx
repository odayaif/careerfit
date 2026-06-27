import React from 'react'

export default function Layout({ header, sidebar, center, rightPanel }) {
  return (
    <div className="app-wrapper">
      <header className="header">{header}</header>
      <div className="main-layout">
        <aside className="sidebar-left scrollable">{sidebar}</aside>
        <main className="center-panel">{center}</main>
        <aside className="sidebar-right scrollable">{rightPanel}</aside>
      </div>
    </div>
  )
}
