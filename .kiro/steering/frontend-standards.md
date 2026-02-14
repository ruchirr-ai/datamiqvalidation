---
inclusion: fileMatch
fileMatchPattern: '**/*.{tsx,ts,jsx,js}'
---

# Frontend Development Standards

## Framework: React

### Component Organization
- Use functional components with hooks
- Organize by feature/module
- Keep components small and focused
- Separate presentational and container components

### Component Library (UI Bundle)
Create a centralized component library with reusable UI components:
- **Location**: `frontend/src/components/ui/`
- **Components**: Button, Input, Form, Link, Card, Modal, Table, etc.
- **Purpose**: Single source of truth for all UI components
- **Usage**: Import and reuse across all features instead of recreating

**Benefits**:
- Consistent styling across the application
- Easier maintenance and updates
- Faster development
- Uniform user experience

### State Management
- Use React hooks for local state
- Consider Context API or state management library for global state
- Keep state as close to where it's used as possible

### API Integration
- Create a dedicated API client layer
- Use async/await for API calls
- Implement proper error handling
- Show loading states during async operations

### UI/UX Principles
- Provide clear feedback for long-running operations (migrations)
- Show progress indicators for multi-step processes
- Implement proper error messages and validation
- Ensure accessibility compliance

### Responsive Design
The UI MUST be compatible with multiple screen sizes:
- **Laptop**: Desktop/laptop screens (1024px and above)
- **iPad**: Tablet screens (768px - 1023px)
- **Mobile**: Mobile screens (320px - 767px)

**Implementation**:
- Use responsive CSS (flexbox, grid)
- Implement mobile-first design approach
- Test on all target screen sizes
- Use media queries for breakpoints
- Ensure touch-friendly UI elements on mobile/tablet

### Design System

#### Color Palette
Use the defined brand color scheme:

**Brand Colors**:
- **Blue 1**: #003087 (Dark Blue - headers, important text)
- **Blue 2**: #0070E0 (Medium Blue - primary actions, links)
- **Blue 3**: #001C64 (Darkest Blue - emphasis)
- **Gold**: #FFD140 (Accent color, highlights)
- **Slate**: #001435 (Dark slate - primary text)
- **Off White**: #FAF8F5 (Background)
- **White**: #FFFFFF (Surface, cards)
- **Black**: #000000 (Use sparingly)
- **Grey**: Various shades for borders, secondary text, disabled states

**Semantic Colors**:
- Success: Green (#4CAF50)
- Error: Red (#F44336)
- Warning: Gold (#FFD140)
- Info: Blue 2 (#0070E0)

**Rules**:
- Don't use too many colors
- Stick to the defined brand palette
- Use grey shades for backgrounds and borders
- Use Blue 2 for primary actions and links
- Use Gold sparingly for accents
- Maintain high contrast for accessibility

#### Icons
- Use minimal, small, outline-based icons (inspired by Snowflake UI)
- Recommended: Lucide React, Heroicons, Feather Icons
- DO NOT use emojis
- Use ONLY outline/stroke style (no filled icons)
- Keep icons small and clean (16px, 20px, 24px)
- Ensure icons are accessible with proper labels

#### Typography
- **Google Sans Flex**: For all UI text, headings, body, buttons
- **Google Sans Code**: ONLY for code blocks and monospace text
- Import from Google Fonts
- Maintain consistent heading hierarchy
- Ensure readable font sizes on all devices

### Code Style
- Use TypeScript for type safety
- Follow consistent naming conventions
- Use ESLint and Prettier
- Write self-documenting code with clear variable names

### Testing
- Write tests for EVERY component and feature
- Include sample data/payloads in all tests
- Write unit tests for utility functions
- Write component tests for UI logic
- Test user interactions and workflows
- Mock API calls in tests
- Minimum 70% code coverage
- Test rendering, interactions, and error states
