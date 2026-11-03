"""Small multi-object tracker: gated global assignment + alpha-beta motion filter.

IDs describe continuous visible tracks, not permanent specimen identities.
"""
from collections import deque
import math
import numpy as np


def wrap_angle(angle):
    return (angle + math.pi / 2) % math.pi - math.pi / 2


class Tracker:
    def __init__(self):
        self.value = None
        self.velocity = np.zeros(3)
        self.last = None

    def update(self, measurement, now):
        measurement = np.array(measurement, dtype=float)
        if self.value is None or now - self.last > 0.8:
            self.value = measurement
            self.velocity[:] = 0
        else:
            dt = max(0.005, min(0.8, now - self.last))
            predicted = self.value + dt * self.velocity
            error = measurement - predicted
            error[2] = wrap_angle(error[2])
            self.value = predicted + 0.78 * error
            self.velocity += 0.10 * error / dt
        self.value[2] = wrap_angle(self.value[2])
        self.last = now
        return self.value.copy()


def assign(costs):
    """Hungarian rectangular assignment. Requires columns >= rows."""
    if not costs:
        return []
    rows, columns = len(costs), len(costs[0])
    if columns < rows:
        raise ValueError('Assignment needs at least as many columns as rows')
    u, v = [0.0] * (rows + 1), [0.0] * (columns + 1)
    matches, previous = [0] * (columns + 1), [0] * (columns + 1)
    for row in range(1, rows + 1):
        matches[0] = row
        minimum, visited = [float('inf')] * (columns + 1), [False] * (columns + 1)
        column = 0
        while True:
            visited[column] = True
            active_row = matches[column]
            delta, next_column = float('inf'), 0
            for j in range(1, columns + 1):
                if not visited[j]:
                    current = costs[active_row - 1][j - 1] - u[active_row] - v[j]
                    if current < minimum[j]:
                        minimum[j], previous[j] = current, column
                    if minimum[j] < delta:
                        delta, next_column = minimum[j], j
            for j in range(columns + 1):
                if visited[j]:
                    u[matches[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            column = next_column
            if matches[column] == 0:
                break
        while True:
            before = previous[column]
            matches[column] = matches[before]
            column = before
            if column == 0:
                break
    result = [-1] * rows
    for j in range(1, columns + 1):
        if matches[j]:
            result[matches[j] - 1] = j - 1
    return result


class MultiTracker:
    def __init__(self, max_age=0.8):
        self.max_age = max_age
        self.tracks = {}
        self.next_id = 1

    def reset(self):
        # Preserve the counter so a settings change does not reuse an old ID.
        self.tracks.clear()

    def cost(self, track, observation, now):
        dt = max(0.0, min(self.max_age, now - track['last']))
        prediction = track['filter'].value[:2] + dt * track['filter'].velocity[:2]
        distance = float(np.linalg.norm(np.asarray(observation['center']) - prediction))
        gate = min(140.0, max(45.0, math.sqrt(track['area']) * 0.8 + 150 * dt))
        area_ratio = observation['area'] / max(track['area'], 1)
        if distance > gate or not 0.40 <= area_ratio <= 2.5:
            return 1000.0
        old_color = track['color']
        new_color = observation['classification']['key']
        color_penalty = 0.55 if old_color != new_color and 'unknown' not in (old_color, new_color) else 0.0
        return distance / gate + 0.35 * abs(math.log(area_ratio)) + color_penalty

    def update(self, observations, now):
        self.tracks = {key: track for key, track in self.tracks.items() if now - track['last'] <= self.max_age}
        observations = sorted(observations, key=lambda item: (item['center'][0], item['center'][1]))
        existing = sorted(self.tracks)
        count = len(observations)
        costs = [[self.cost(self.tracks[key], item, now) for item in observations] + [1.10] * len(existing)
                 for key in existing]
        assignments = assign(costs)
        owners = {}
        for row, column in enumerate(assignments):
            if 0 <= column < count and costs[row][column] < 1.10:
                owners[column] = existing[row]
        visible = []
        for index, observation in enumerate(observations):
            ident = owners.get(index)
            if ident is None:
                ident = self.next_id
                self.next_id += 1
                self.tracks[ident] = {'filter': Tracker(), 'trail': deque(maxlen=30)}
            track = self.tracks[ident]
            values = track['filter'].update((*observation['center'], observation['angle']), now)
            track['trail'].append((int(round(values[0])), int(round(values[1]))))
            track.update(last=now, area=observation['area'], color=observation['classification']['key'])
            visible.append(dict(observation, track_id=ident, filtered=values, trail=list(track['trail'])))
        # Lost tracks are retained briefly for matching, but never returned as visible targets.
        if len(self.tracks) > 36:
            keep = sorted(self.tracks, key=lambda key: self.tracks[key]['last'], reverse=True)[:36]
            self.tracks = {key: self.tracks[key] for key in keep}
        return sorted(visible, key=lambda item: item['track_id'])
