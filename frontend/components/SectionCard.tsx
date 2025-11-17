import { useState } from 'react';
import { Section } from '@/lib/types';

interface SectionCardProps {
  section: Section;
  onToggle: (id: number) => void;
  onUpdate: (id: number, text: string) => void;
  onRemove: (id: number) => void;
}

export default function SectionCard({
  section,
  onToggle,
  onUpdate,
  onRemove,
}: SectionCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(section.text);

  const handleSave = () => {
    onUpdate(section.id, editText);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditText(section.text);
    setIsEditing(false);
  };

  return (
    <div className={`section-card ${!section.enabled && 'opacity-50'}`}>
      <div className="flex items-start gap-4">
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={section.enabled}
          onChange={() => onToggle(section.id)}
          className="mt-1 h-5 w-5 text-primary focus:ring-primary rounded"
        />

        {/* Content */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-gray-800">
              Section {section.id + 1}
            </h3>
            <div className="flex gap-2">
              {!isEditing ? (
                <>
                  <button
                    onClick={() => setIsEditing(true)}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => onRemove(section.id)}
                    className="text-sm text-red-600 hover:text-red-800 font-medium"
                  >
                    Remove
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={handleSave}
                    className="text-sm text-green-600 hover:text-green-800 font-medium"
                  >
                    Save
                  </button>
                  <button
                    onClick={handleCancel}
                    className="text-sm text-gray-600 hover:text-gray-800 font-medium"
                  >
                    Cancel
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Text */}
          {isEditing ? (
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="input font-mono text-sm min-h-[100px]"
              autoFocus
            />
          ) : (
            <p className="text-gray-700 text-sm whitespace-pre-wrap font-mono leading-relaxed">
              {section.text.length > 200
                ? section.text.slice(0, 200) + '...'
                : section.text}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
