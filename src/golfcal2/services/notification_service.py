"""Notification service for golf calendar application."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from golfcal2.config.settings import AppConfig
from golfcal2.models.reservation import Player, Reservation
from golfcal2.services.pushover_service import PushoverService
from golfcal2.utils.logging_utils import LoggerMixin


@dataclass
class PlayerChange:
    """Represents a change in players for a reservation."""
    added: list[Player]
    removed: list[Player]
    reservation: Reservation
    timestamp: datetime

class NotificationService(LoggerMixin):
    """Service for handling notifications about changes in reservations."""
    
    def __init__(self, config: AppConfig):
        """Initialize notification service."""
        super().__init__()
        self.config = config
        self.data_dir = Path(config.get('data_dir', 'data'))
        self.state_file = self.data_dir / 'reservation_state.json'
        self.pushover = PushoverService(config)
        self._ensure_data_dir()
    
    def _ensure_data_dir(self) -> None:
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_state(self) -> dict[str, list[dict[str, Any]]]:
        """Load previous state from file."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            return {}
    
    def _save_state(self, state: dict[str, list[dict[str, Any]]]) -> None:
        """Save current state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def _player_to_dict(self, player: Player) -> dict[str, Any]:
        """Convert player to dictionary for storage."""
        return {
            'name': player.name,
            'club': player.club,
            'handicap': player.handicap
        }
    
    def _dict_to_player(self, data: dict[str, Any]) -> Player:
        """Convert dictionary to player."""
        return Player(
            name=data['name'],
            club=data['club'],
            handicap=data['handicap']
        )
    
    def _get_player_set(self, players: list[Player]) -> set[str]:
        """Convert list of players to set of player identifiers."""
        return {f"{p.name}|{p.club}" for p in players}
    
    def check_for_changes(self, reservations: list[Reservation]) -> list[PlayerChange]:
        """Check for changes in players for the given reservations."""
        changes: list[PlayerChange] = []
        state = self._load_state()
        new_state: dict[str, list[dict[str, Any]]] = {}
        
        # Process each reservation
        for reservation in reservations:
            # Skip past reservations
            if reservation.start_time < datetime.now(reservation.start_time.tzinfo):
                continue
                
            # Convert current players to storable format
            current_players = [self._player_to_dict(p) for p in reservation.players]
            new_state[reservation.uid] = current_players
            
            # Get previous players
            prev_players_data = state.get(reservation.uid, [])
            prev_players = [self._dict_to_player(p) for p in prev_players_data]
            
            # Compare players
            current_set = self._get_player_set(reservation.players)
            prev_set = self._get_player_set(prev_players)
            
            # Find added and removed players
            added_set = current_set - prev_set
            removed_set = prev_set - current_set
            
            if added_set or removed_set:
                # Get full player objects for added/removed players
                added = [p for p in reservation.players if f"{p.name}|{p.club}" in added_set]
                removed = [p for p in prev_players if f"{p.name}|{p.club}" in removed_set]
                
                change = PlayerChange(
                    added=added,
                    removed=removed,
                    reservation=reservation,
                    timestamp=datetime.now(reservation.start_time.tzinfo)
                )
                changes.append(change)
                
                # Send Pushover notification for the change
                if self.pushover.is_enabled():
                    title = f"Player Changes - {reservation.club.name}"
                    message = self.format_change_message(change)
                    self.pushover.send_notification(title=title, message=message)
        
        # Save new state
        self._save_state(new_state)
        
        return changes
    
    def format_change_message(self, change: PlayerChange) -> str:
        """Format a change notification message."""
        lines = [
            f"Changes in reservation at {change.reservation.club.name}",
            f"Time: {change.reservation.start_time.strftime('%Y-%m-%d %H:%M')}"
        ]
        
        if change.added:
            lines.append("\nPlayers added:")
            for player in change.added:
                lines.append(f"- {player.name} ({player.club}, HCP: {player.handicap})")
        
        if change.removed:
            lines.append("\nPlayers removed:")
            for player in change.removed:
                lines.append(f"- {player.name} ({player.club}, HCP: {player.handicap})")
        
        return "\n".join(lines) 